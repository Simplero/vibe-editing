#!/usr/bin/env python3
"""
highlight_reframe16.py — single-face 16:9 -> 16:9 face-tracked PUNCH-IN (for Q&A mids).

Adapted from the reframe engine (YuNet detect → smoothed trajectory → Y-lock eyeline →
per-frame crop following the subject). The ONLY structural change vs the 9:16 reframe is the
crop aspect: 16:9 (cropW = cropH*16/9) with a 1920x1080 (or 4K) output, instead of 9:16. This
keeps a moving subject (a host pacing a stage, or a guest at the mic) centered and well-sized
full-screen — logic + keyframing instead of a static crop that loses them.

Presets (16:9, tuned for a stage Q&A):
  host16   : host on stage (paces) — zoom 1.5, ROI excludes the audience foreground, X FOLLOWS.
  guest16  : guest at the floor mic (fairly static) — zoom 1.4, center ROI.
  wide16   : a WIDE audience/reaction cam used as the "guest" angle on rigs that have NO
             dedicated tight questioner cam. zoom 1.0 = full-frame passthrough — never punches
             in onto a random non-speaking attendee.
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
_sys.path.insert(0, _os.path.join(VIBE_ROOT, "lib", "_shared"))
YUNET = _os.path.join(VIBE_ROOT, "skills", "horizontal-to-vertical", "scripts", "yunet.onnx")
# ── end bootstrap ──
import cv2, numpy as np, subprocess, argparse
from fast_encode import encoder_args

PRESETS = {
    "host16":  {"zoom": 1.5, "eye_y": 0.30, "roi": [0.20, 0.00, 1.00, 0.62], "lock_y": True, "lock_x": False},
    "guest16": {"zoom": 1.4, "eye_y": 0.34, "roi": [0.18, 0.08, 0.82, 0.66], "lock_y": True, "lock_x": False},
    "wide16":  {"zoom": 1.0, "eye_y": 0.50, "roi": [0.0, 0.0, 1.0, 1.0], "lock_y": True, "lock_x": True},
}
ap = argparse.ArgumentParser()
ap.add_argument("inp"); ap.add_argument("out")
ap.add_argument("--preset", choices=sorted(PRESETS))
ap.add_argument("--res", default="1080", choices=["1080", "4k"])
ap.add_argument("--zoom", type=float, default=None)
ap.add_argument("--eye-y", type=float, default=None, dest="eye_y")
ap.add_argument("--roi", type=float, nargs=4, default=None)
ap.add_argument("--detw", type=int, default=1280)
ap.add_argument("--face-conf", type=float, default=0.5, dest="face_conf")
ap.add_argument("--smooth", type=int, default=41)
ap.add_argument("--lock-y", action="store_true", dest="lock_y", default=None)
ap.add_argument("--lock-x", action="store_true", dest="lock_x", default=None)
ap.add_argument("--model", default=YUNET)
a = ap.parse_args()
_p = PRESETS[a.preset] if a.preset else {}
if a.zoom is None:   a.zoom = _p.get("zoom", 1.4)
if a.eye_y is None:  a.eye_y = _p.get("eye_y", 0.30)
if a.roi is None:    a.roi = _p.get("roi", [0.10, 0.00, 0.95, 0.62])
if a.lock_y is None: a.lock_y = _p.get("lock_y", True)
if a.lock_x is None: a.lock_x = _p.get("lock_x", False)

cap = cv2.VideoCapture(a.inp); W = int(cap.get(3)); H = int(cap.get(4)); fps = cap.get(5) or 24.0
dw = min(a.detw, W); sc = dw / W; dh = int(H * sc)
det = cv2.FaceDetectorYN.create(a.model, "", (dw, dh), 0.3, 0.3, 5000)
rx0, ry0, rx1, ry1 = a.roi; R = (rx0 * dw, ry0 * dh, rx1 * dw, ry1 * dh)
xs, ys, last, hits, n = [], [], None, 0, 0
while True:
    ok, fr = cap.read()
    if not ok: break
    small = cv2.resize(fr, (dw, dh)); n += 1
    _, faces = det.detect(small); cand = []
    if faces is not None:
        for f in faces:
            cx, cy = f[0] + f[2] / 2, f[1] + f[3] / 2
            if R[0] <= cx <= R[2] and R[1] <= cy <= R[3] and f[-1] >= a.face_conf:
                cand.append(f)
    pick = None
    if cand:
        if last is not None:
            pick = min(cand, key=lambda f: abs(f[8] - last))
            if abs(pick[8] - last) > 0.15 * dw:
                pick = max(cand, key=lambda f: f[2] * f[3] * f[-1])
        else:
            pick = max(cand, key=lambda f: f[2] * f[3] * f[-1])
    if pick is not None:
        xc = pick[0] + pick[2] / 2
        xs.append(xc / sc); ys.append(float(pick[5] + pick[7]) / 2 / sc); last = float(pick[8]); hits += 1
    else:
        xs.append(np.nan); ys.append(np.nan)
cap.release()
xs, ys = np.array(xs, float), np.array(ys, float); idx = np.arange(n); good = ~np.isnan(xs)
if good.sum() == 0:
    xs[:] = (rx0 + rx1) / 2 * W; ys[:] = (ry0 + ry1) / 2 * H
    print("  no face in ROI -> static ROI-center fallback")
else:
    xs = np.interp(idx, idx[good], xs[good]); ys = np.interp(idx, idx[good], ys[good])
def smooth(arr, win):
    win = max(3, win | 1); m = arr.copy()
    for i in range(len(arr)): m[i] = np.median(arr[max(0, i - 2):i + 3])
    pad = np.pad(m, (win // 2, win // 2), mode="edge"); return np.convolve(pad, np.ones(win) / win, mode="valid")[:len(arr)]
xss, yss = smooth(xs, a.smooth), smooth(ys, a.smooth)
if a.lock_x: xss[:] = float(np.median(xss))
OW, OH = (3840, 2160) if a.res == "4k" else (1920, 1080)
cropH = min(H, int(round(H / a.zoom))); cropW = min(W, int(round(cropH * 16 / 9)))
y_lock = float(np.median(yss)) if a.lock_y else None
print(f"{W}x{H} {fps:.1f}fps {n}f | hits {hits} ({100*hits//max(1,n)}%) | crop {cropW}x{cropH} | "
      f"x {xss.min()/W:.2f}-{xss.max()/W:.2f} | y {'LOCK@%.2f'%(y_lock/H) if a.lock_y else 'track'}", flush=True)
ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr24",
    "-s", f"{OW}x{OH}", "-r", f"{fps}", "-i", "-", "-i", a.inp, "-map", "0:v", "-map", "1:a?",
    *encoder_args(OW, OH, "ffmpeg", tier="intermediate"), "-c:a", "aac", "-b:a", "192k",
    "-movflags", "+faststart", a.out], stdin=subprocess.PIPE)
cap = cv2.VideoCapture(a.inp)
for i in range(n):
    ok, fr = cap.read()
    if not ok: break
    x0 = max(0, min(W - cropW, int(round(xss[i] - cropW / 2))))
    yc = y_lock if a.lock_y else yss[i]
    y0 = max(0, min(H - cropH, int(round(yc - a.eye_y * cropH))))
    crop = fr[y0:y0 + cropH, x0:x0 + cropW]
    ff.stdin.write(cv2.resize(crop, (OW, OH), interpolation=cv2.INTER_LANCZOS4).tobytes())
ff.stdin.close(); ff.wait(); cap.release()
print("reframe16 ->", a.out)
