#!/usr/bin/env python3
"""shot_check — score how *clippable a moment's SHOT is*, using the bundled YuNet detector.

Catches the #1 selection mistake: clipping a side-profile / off-angle / wide / wrong-person
moment that has great WORDS but looks bad as a vertical short. Run it at PICK time on each
candidate [--start,--end] window and only ship windows that come back GOOD. Key-free (YuNet
ships with the kit) — no API needed.

Reports (sampled across the window):
  face_present   fraction of frames with a detectable face
  frontality     0..1 — how face-on the dominant face is (low = profile / turned away)
  face_size      dominant face height as a fraction of frame height (low = wide shot)
  single_subject fraction of frames with one clear dominant face (low = multi-person / cutting)
  verdict        GOOD | PROFILE | WIDE | MULTI | NO_FACE
"""
import argparse, json, sys
from pathlib import Path


def _plugin_root() -> Path:
    d = Path(__file__).resolve()
    for p in (d, *d.parents):
        if (p / ".claude-plugin").is_dir():
            return p
    return d.parents[3]


def main() -> int:
    ap = argparse.ArgumentParser(description="Score a moment's shot for clippability (face-on, size, single subject).")
    ap.add_argument("video")
    ap.add_argument("--start", type=float, default=None)
    ap.add_argument("--end", type=float, default=None)
    ap.add_argument("--frames", type=int, default=8, help="frames to sample across the window")
    ap.add_argument("--model", default=None)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    import cv2
    model = a.model or str(_plugin_root() / "skills/horizontal-to-vertical/scripts/yunet.onnx")
    cap = cv2.VideoCapture(a.video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    nfr = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
    dur = (nfr / fps) if nfr else 0.0
    s = a.start if a.start is not None else 0.0
    e = a.end if a.end is not None else dur
    if e <= s:
        e = s + 1.0
    ts = [s + (e - s) * i / max(1, a.frames - 1) for i in range(a.frames)]

    fd = cv2.FaceDetectorYN.create(model, "", (320, 320), 0.6)
    n = present = 0
    fronts, sizes, singles = [], [], []
    for t in ts:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, frm = cap.read()
        if not ok:
            continue
        n += 1
        h, w = frm.shape[:2]
        fd.setInputSize((w, h))
        _, faces = fd.detect(frm)
        if faces is None or len(faces) == 0:
            fronts.append(0.0); sizes.append(0.0); singles.append(0.0)
            continue
        present += 1
        faces = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)
        big = faces[0]
        fw, fh = big[2], big[3]
        rex, lex, nx = big[4], big[6], big[8]      # right-eye x, left-eye x, nose x
        eye_mid = (rex + lex) / 2.0
        eye_d = abs(rex - lex)
        nose_off = abs(nx - eye_mid) / (eye_d + 1e-6)   # frontal ~0–0.2, profile large
        eye_ratio = eye_d / (fw + 1e-6)                  # frontal ~0.4–0.5, profile small
        f_on = 1.0
        if nose_off > 0.35 or eye_ratio < 0.30:
            f_on = 0.0
        elif nose_off > 0.22 or eye_ratio < 0.37:
            f_on = 0.5
        fronts.append(f_on)
        sizes.append(fh / h)
        second = faces[1][2] * faces[1][3] if len(faces) > 1 else 0
        singles.append(1.0 if second < 0.4 * (fw * fh) else 0.0)
    cap.release()

    if n == 0:
        print(json.dumps({"verdict": "NO_FRAMES"})); return 0
    res = {
        "window": [round(s, 2), round(e, 2)],
        "face_present": round(present / n, 2),
        "frontality": round(sum(fronts) / len(fronts), 2),
        "face_size": round(sum(sizes) / len(sizes), 2),
        "single_subject": round(sum(singles) / len(singles), 2),
    }
    if res["face_present"] < 0.5:
        v = "NO_FACE"
    elif res["frontality"] < 0.5:
        v = "PROFILE"
    elif res["face_size"] < 0.10:
        v = "WIDE"
    elif res["single_subject"] < 0.6:
        v = "MULTI"
    else:
        v = "GOOD"
    res["verdict"] = v
    res["clippable"] = (v == "GOOD")
    print(json.dumps(res, indent=2) if a.json else
          f"{v}  ·  frontality {res['frontality']} · present {res['face_present']} · "
          f"size {res['face_size']} · single {res['single_subject']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
