#!/usr/bin/env python3
"""layout_analyze — decide caption Y by LOOKING AT THE FOOTAGE, per camera angle.

The captions engine (spice_caption.py) calls this on the BURN input (the reframed
9:16 video) to get a per-segment caption Y that clears the speaker's face. Without
it, generate_spice falls back to the preset's STATIC y_percent_from_top — which on a
tight talking-head reframe lands the caption straight across the eyes (Operator, Calvin
2026-07-05: "the captions are right over my eyes ... look at the footage to determine
the best placement"). This module is that "look at the footage" step.

Method: YuNet face detection (the kit's own detector) across sampled frames -> a smoothed
chin track -> split into segments at real camera cuts (big face jumps) -> per segment,
place the caption a margin BELOW the lowest the chin goes (high percentile, so a head-bob
doesn't clip it), clamped into the platform safe zone (never below ~86%, never up into the
face). If a segment has no reliable face, fall back to a lower-third default (~80%). If the
face fills the frame to the bottom, place ABOVE the head instead.

CLI:  layout_analyze.py INPUT_VIDEO OUTPUT_JSON [--sample-every N] [--model path]
Out:  {"meta": {...}, "segments": [{"start_i": int, "end_i": int, "safe_y_pct": float}]}
      safe_y_pct = caption vertical CENTER as a 0..1 fraction of frame height.
"""
# ── vibe-editing portable path bootstrap ──
import os as _os, sys as _sys, pathlib as _pl
def _acq_root():
    r = _os.environ.get("VIBE_PIPELINE_ROOT") or _os.environ.get("CLAUDE_PLUGIN_ROOT")
    if r and _os.path.isdir(_os.path.join(r, ".claude-plugin")):
        return r
    d = _os.path.dirname(_os.path.abspath(__file__))
    while d != _os.path.dirname(d):
        if _os.path.isdir(_os.path.join(d, ".claude-plugin")):
            return d
        d = _os.path.dirname(d)
    return _os.path.dirname(_os.path.abspath(__file__))
VIBE_ROOT = _acq_root()
def _acq(p):
    return _pl.Path(_os.path.join(VIBE_ROOT, "skills", *[x for x in str(p).strip("/").split("/") if x]))
# ── end bootstrap ──
# The caption engine shells out with a bare `python3` that may lack OpenCV (cv2 lives in
# the kit venv). If so, re-exec THIS script under the venv interpreter so detection works.
try:
    import cv2  # noqa: F401
except ImportError:
    # NB: compare LITERAL paths, not realpath — a venv's python is a symlink to the base
    # interpreter, but launching it by its venv path is what activates the venv site-packages.
    _venv = _os.path.join(VIBE_ROOT, ".venv", "bin", "python")
    if _os.path.exists(_venv) and _os.path.abspath(_venv) != _os.path.abspath(_sys.executable):
        _os.execv(_venv, [_venv, _os.path.abspath(__file__), *_sys.argv[1:]])
    raise
import cv2, numpy as np, json, argparse, sys

# --- Placement tuning (fractions of frame height) ---------------------------
CHIN_PCTL     = 90     # use the 90th-pct chin position, so brief head-bobs don't clip the caption
GAP_BELOW_CHIN = 0.045 # breathing room between chin and caption center
SAFE_BOTTOM   = 0.86   # caption CENTER never lower than this (keeps text off the platform UI band)
SAFE_TOP_BELOW = 0.55  # when placing below the face, never come back UP past this (stay clear of eyes)
NOFACE_DEFAULT = 0.80  # lower-third default when no face is found in a segment
ABOVE_MARGIN  = 0.05   # gap above the head when forced to place above the face
CUT_JUMP      = 0.14   # face center-x/chin jump (frac) between samples that signals a real camera cut
MIN_SEG_FRAMES = 8     # don't emit micro-segments


def detect_track(inp, sample_every, model):
    cap = cv2.VideoCapture(inp)
    W = int(cap.get(3)); H = int(cap.get(4)); fps = cap.get(5) or 30.0
    N = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
    dw = 960; sc = dw / max(1, W); dh = int(H * sc)
    det = cv2.FaceDetectorYN.create(model, "", (dw, dh), 0.6, 0.3, 5000)
    chin = np.full(N if N else 100000, np.nan)   # face-box bottom, frac of H
    top  = np.full_like(chin, np.nan)            # face-box top, frac of H
    cx   = np.full_like(chin, np.nan)            # face center x, frac of W
    i = 0; last = 0
    while True:
        ok, fr = cap.read()
        if not ok: break
        if i % sample_every == 0:
            small = cv2.resize(fr, (dw, dh)); _, faces = det.detect(small)
            if faces is not None and len(faces):
                f = max(faces, key=lambda r: r[14])  # highest-score face = the subject
                x, y, w, h = (float(f[0]) / sc, float(f[1]) / sc,
                              float(f[2]) / sc, float(f[3]) / sc)
                chin[i] = (y + h) / H; top[i] = y / H; cx[i] = (x + w / 2) / W
            last = i
        i += 1
    cap.release()
    n = last + 1
    return chin[:n], top[:n], cx[:n], W, H, fps, n


def segment(cx, chin, n):
    """Split into [start_i, end_i] runs at real camera cuts (big face jumps)."""
    # interpolate small gaps so a single missed detection isn't read as a cut
    idx = np.arange(n)
    def fill(a):
        g = ~np.isnan(a)
        return np.interp(idx, idx[g], a[g]) if g.any() else a
    cxf, chf = fill(cx), fill(chin)
    cuts = [0]
    for i in range(1, n):
        if abs(cxf[i] - cxf[i - 1]) > CUT_JUMP or abs(chf[i] - chf[i - 1]) > CUT_JUMP:
            if i - cuts[-1] >= MIN_SEG_FRAMES:
                cuts.append(i)
    cuts.append(n)
    return [(cuts[k], cuts[k + 1] - 1) for k in range(len(cuts) - 1)]


def place(chin_seg, top_seg):
    """Given the chin/top fracs within one segment, return the caption-center safe_y_pct."""
    good = ~np.isnan(chin_seg)
    if good.sum() < 3:
        return NOFACE_DEFAULT
    chin_lo = float(np.percentile(chin_seg[good], CHIN_PCTL))  # lowest the chin realistically goes
    y = chin_lo + GAP_BELOW_CHIN
    if y <= SAFE_BOTTOM:
        return round(max(SAFE_TOP_BELOW, min(SAFE_BOTTOM, y)), 4)
    # Face runs to the bottom of frame — no clean band below the chin. Place above the head.
    top_hi = float(np.percentile(top_seg[~np.isnan(top_seg)], 100 - CHIN_PCTL)) if (~np.isnan(top_seg)).any() else 0.2
    return round(max(0.12, top_hi - ABOVE_MARGIN), 4)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inp"); ap.add_argument("out")
    ap.add_argument("--sample-every", type=int, default=1)
    ap.add_argument("--model", default=str(_acq("horizontal-to-vertical/scripts/yunet.onnx")))
    a = ap.parse_args()

    chin, top, cx, W, H, fps, n = detect_track(a.inp, max(1, a.sample_every), a.model)
    if n == 0:
        json.dump({"meta": {"fps": fps, "w": W, "h": H, "note": "empty"}, "segments": []}, open(a.out, "w"))
        print("layout_analyze: no frames", file=sys.stderr); return 0

    segs_idx = segment(cx, chin, n)
    segments = []
    for (s, e) in segs_idx:
        y = place(chin[s:e + 1], top[s:e + 1])
        segments.append({"start_i": int(s), "end_i": int(e), "safe_y_pct": y})
    faces_found = int((~np.isnan(chin)).sum())
    out = {"meta": {"fps": float(fps), "w": W, "h": H, "frames": n,
                    "faces_found": faces_found, "method": "yunet-below-chin"},
           "segments": segments}
    json.dump(out, open(a.out, "w"), indent=1)
    rng = f"{min(s['safe_y_pct'] for s in segments):.3f}-{max(s['safe_y_pct'] for s in segments):.3f}"
    print(f"layout_analyze: {len(segments)} segment(s), Y {rng} of H "
          f"({faces_found}/{n} frames had a face)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
