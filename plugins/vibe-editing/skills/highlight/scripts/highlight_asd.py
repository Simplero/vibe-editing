#!/usr/bin/env python3
"""
highlight_asd.py — visual Active-Speaker Detection for two-cam Q&A switching.

When the board-mix cam audio can't separate the two speakers (highlight_diarize reports "mics
DON'T separate"), detect the speaker VISUALLY, reusing the same YuNet model as
highlight_reframe16: on each cam, track the face and measure MOUTH-region motion, normalized by
upper-face (brow/eye) motion so that someone pacing/gesturing/turning their head does NOT read
as talking. Whoever's mouth is moving = talking -> camera-switch EDL.

  A-cam face = "host",  B-cam face = "guest".

Outputs a fine EDL (A-cam-absolute, contiguous) for highlight_multicam.py. With --ref <edl>,
prints time-aligned agreement vs a reference EDL (used to validate against a hand-labeled EDL).
"""
# ── vibe-editing portable path bootstrap ──
import os as _os, sys as _sys
def _vibe_root():
    r = _os.environ.get("VIBE_PIPELINE_ROOT") or _os.environ.get("CLAUDE_PLUGIN_ROOT")
    if r and _os.path.isdir(_os.path.join(r, ".claude-plugin")):
        return r
    d = _os.path.dirname(_os.path.abspath(__file__))
    while d != _os.path.dirname(d):
        if _os.path.isdir(_os.path.join(d, ".claude-plugin")):
            return d
        d = _os.path.dirname(d)
    return _os.path.dirname(_os.path.abspath(__file__))
VIBE_ROOT = _vibe_root()
MODEL = _os.path.join(VIBE_ROOT, "skills", "horizontal-to-vertical", "scripts", "yunet.onnx")
# ── end bootstrap ──
import cv2, numpy as np, json, argparse

ROI = {"host": [0.20, 0.00, 1.00, 0.62], "guest": [0.18, 0.08, 0.82, 0.66]}


def track_mouth(path, t0, dur, roi, fps_sample=12, detw=640):
    """Sample the segment; return (times[], talk[], present[]) where talk = lower/upper face-motion ratio."""
    cap = cv2.VideoCapture(path)
    fps = cap.get(5) or 24.0
    W = int(cap.get(3)); H = int(cap.get(4))
    cap.set(cv2.CAP_PROP_POS_MSEC, t0 * 1000.0)
    dw = min(detw, W); sc = dw / W; dh = int(H * sc)
    det = cv2.FaceDetectorYN.create(MODEL, "", (dw, dh), 0.3, 0.3, 5000)
    rx0, ry0, rx1, ry1 = roi; R = (rx0 * dw, ry0 * dh, rx1 * dw, ry1 * dh)
    step = max(1, int(round(fps / fps_sample)))
    times, talk, present = [], [], []
    prev_l = prev_u = None; last = None; fidx = 0; nframes = int(dur * fps)
    while fidx < nframes:
        ok, fr = cap.read()
        if not ok:
            break
        if fidx % step == 0:
            small = cv2.resize(fr, (dw, dh)); gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            _, faces = det.detect(small); cand = []
            if faces is not None:
                for f in faces:
                    cx, cy = f[0] + f[2] / 2, f[1] + f[3] / 2
                    if R[0] <= cx <= R[2] and R[1] <= cy <= R[3] and f[-1] >= 0.5:
                        cand.append(f)
            pick = None
            if cand:
                pick = (min(cand, key=lambda f: abs(f[0] + f[2] / 2 - last)) if last is not None
                        else max(cand, key=lambda f: f[2] * f[3] * f[-1]))
                last = pick[0] + pick[2] / 2
            else:
                last = None
            t = t0 + fidx / fps; sc_val = 0.0; pr = 0
            if pick is not None:
                x, y, w, h = [max(0, int(v)) for v in pick[:4]]
                face = gray[y:y + h, x:x + w]
                if face.size > 0 and h >= 8 and w >= 8:
                    half = max(1, h // 2)
                    u = cv2.resize(face[:half, :], (48, 24)).astype(np.float32)
                    l = cv2.resize(face[half:, :], (48, 24)).astype(np.float32)
                    if prev_l is not None:
                        lm = float(np.mean(np.abs(l - prev_l)))
                        um = float(np.mean(np.abs(u - prev_u)))
                        sc_val = lm / (um + 2.0)        # mouth moves MORE than brow => talking
                    prev_l, prev_u = l, u; pr = 1
                else:
                    prev_l = prev_u = None
            else:
                prev_l = prev_u = None
            times.append(t); talk.append(sc_val); present.append(pr)
        fidx += 1
    cap.release()
    return np.array(times), np.array(talk), np.array(present)


def med(a, k):
    k = max(1, k | 1); pad = np.pad(a, (k // 2, k // 2), mode="edge")
    return np.array([np.median(pad[i:i + k]) for i in range(len(a))])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--acam", required=True); ap.add_argument("--bcam", required=True)
    ap.add_argument("--offset-b", type=float, required=True)
    ap.add_argument("--start", type=float, required=True); ap.add_argument("--end", type=float, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--min-block", type=float, default=1.6)
    ap.add_argument("--thr", type=float, default=0.6)       # min talk-score to count as speaking
    ap.add_argument("--ratio", type=float, default=1.15)    # winner must beat loser by this factor
    ap.add_argument("--ref", default=None)
    a = ap.parse_args()
    dur = a.end - a.start
    ta, sa, pa = track_mouth(a.acam, a.start, dur, ROI["host"])
    tb, sb, pb = track_mouth(a.bcam, a.start + a.offset_b, dur, ROI["guest"])
    # common 0.1s grid (relative to seg start)
    grid = np.arange(0, dur, 0.1)
    rel_a = ta - a.start; rel_b = tb - (a.start + a.offset_b)
    A = np.interp(grid, rel_a, sa, left=0, right=0); B = np.interp(grid, rel_b, sb, left=0, right=0)
    A = med(A, 13); B = med(B, 13)                          # ~1.3s smoothing
    spk = []; prev = "guest"
    for i in range(len(grid)):
        al, gu = A[i], B[i]
        if al >= a.thr and al >= gu * a.ratio:
            s = "host"
        elif gu >= a.thr and gu >= al * a.ratio:
            s = "guest"
        else:
            s = prev                                        # silence/tie -> hold
        spk.append(s); prev = s
    spk = [spk[int(np.clip(j, 0, len(spk) - 1))] for j in range(len(spk))]
    # grid -> blocks, enforce min-block (absorb flickers), emit abs contiguous
    blocks = []
    for i, s in enumerate(spk):
        t = a.start + grid[i]
        if blocks and blocks[-1]["shot"] == s:
            blocks[-1]["end"] = t + 0.1
        else:
            blocks.append({"start": t, "end": t + 0.1, "shot": s})
    out = []
    for b in blocks:
        if out and (b["end"] - b["start"]) < a.min_block:
            out[-1]["end"] = b["end"]
        elif out and out[-1]["shot"] == b["shot"]:
            out[-1]["end"] = b["end"]
        else:
            out.append(dict(b))
    fin = []
    for b in out:
        if fin and fin[-1]["shot"] == b["shot"]:
            fin[-1]["end"] = b["end"]
        else:
            fin.append(dict(b))
    for i in range(len(fin) - 1):
        fin[i]["end"] = fin[i + 1]["start"]
    fin[0]["start"] = a.start; fin[-1]["end"] = a.end
    fin = [{"start": round(b["start"], 3), "end": round(b["end"], 3), "shot": b["shot"]} for b in fin]
    json.dump({"blocks": fin}, open(a.out, "w"), indent=1)
    g = sum(1 for b in fin if b["shot"] == "guest")
    print(f"[asd] {len(fin)} blocks ({g} guest / {len(fin)-g} host), faces a={pa.mean()*100:.0f}% g={pb.mean()*100:.0f}%")

    if a.ref:
        ref = json.load(open(a.ref)); ref = ref["blocks"] if isinstance(ref, dict) else ref
        def at(edl, t):
            for b in edl:
                if b["start"] <= t < b["end"]:
                    return b["shot"]
            return edl[-1]["shot"]
        agree = sum(1 for t in (a.start + grid) if at(fin, t) == at(ref, t)) / len(grid)
        print(f"[asd] agreement vs ref = {agree*100:.1f}%  ({a.ref.split('/')[-1]})")


if __name__ == "__main__":
    main()
