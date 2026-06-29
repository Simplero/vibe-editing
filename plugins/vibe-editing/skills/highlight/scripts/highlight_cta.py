#!/usr/bin/env python3
"""
highlight_cta.py — append YOUR OWN CTA outro to a finished mid (OPTIONAL).

The CTA is user-supplied: drop a short outro clip at  brand/cta/outro.mp4  (repo root) — your
"subscribe / grab the free guide / book a call" ask — and it gets appended to every mid. No
file there? This SKIPS gracefully (exit 0) — the CTA is optional, never required.

Scales the CTA to the mid's WxH/fps and HARD-cuts it on right after the payoff (the payoff
hard-ends, THEN the CTA — no fade on the payoff itself). Re-encodes because the two sources
differ; matches loudness to the mid.
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
VIBE_SHARED = _os.path.join(VIBE_ROOT, "lib", "_shared")
if VIBE_SHARED not in _sys.path:
    _sys.path.insert(0, VIBE_SHARED)
# ── end bootstrap ──
import argparse, json, subprocess, sys

try:
    from fast_encode import encoder_args
except Exception:
    encoder_args = None


def default_cta():
    """The recipient's own outro, staged at the repo-root brand/ folder.
    Search order: env VIBE_BRAND -> repo brand/cta/outro.mp4 -> plugin-relative ../../../brand."""
    cands = []
    env = _os.environ.get("VIBE_BRAND")
    if env:
        cands.append(_os.path.join(env, "cta", "outro.mp4"))
    # repo root is the parent of the plugins/ dir; VIBE_ROOT is the plugin dir
    cands.append(_os.path.join(_os.path.dirname(_os.path.dirname(VIBE_ROOT)), "brand", "cta", "outro.mp4"))
    cands.append(_os.path.join(VIBE_ROOT, "brand", "cta", "outro.mp4"))
    for c in cands:
        if _os.path.exists(c):
            return c
    return cands[0]


def probe(p):
    o = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height,r_frame_rate", "-show_entries", "format=duration",
        "-of", "json", p]).decode())
    s = o["streams"][0]; num, den = s["r_frame_rate"].split("/")
    fps = round(float(num) / float(den)) if float(den) else 30
    return int(s["width"]), int(s["height"]), fps or 30, float(o["format"]["duration"])


def venc(w, h):
    if encoder_args:
        try:
            return list(encoder_args(w, h, "ffmpeg", tier="delivery"))
        except Exception:
            pass
    return ["-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mid", required=True)
    ap.add_argument("--cta", default=None, help="outro clip (default: brand/cta/outro.mp4)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--xfade", type=float, default=0.0, help="seconds of crossfade (0 = hard cut)")
    ap.add_argument("--match-loudness", action="store_true",
                    help="loudnorm the outro to -16 LUFS so it matches the mid (recommended for raw outros)")
    a = ap.parse_args()
    cta = a.cta or default_cta()
    if not _os.path.exists(cta):
        # Optional, never required: no outro present -> just pass the mid through unchanged.
        print(f"[cta] no outro at {cta} — skipping CTA (optional). Passing the mid through unchanged.")
        if _os.path.abspath(a.mid) != _os.path.abspath(a.out):
            import shutil; shutil.copyfile(a.mid, a.out)
        return 0
    w, h, fps, mdur = probe(a.mid)
    norm = (f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
            f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps},format=yuv420p")
    a_post = ":I=-16:LRA=11:TP=-1.5" if a.match_loudness else ""
    a1_filter = (f"[1:a]aformat=sample_rates=48000:channel_layouts=stereo"
                 + (f",loudnorm{a_post}" if a.match_loudness else "") + "[a1]")
    if a.xfade > 0:
        off = max(0.0, mdur - a.xfade)
        fc = (f"[0:v]{norm}[v0];[1:v]{norm}[v1];[v0][v1]xfade=transition=fade:duration={a.xfade}:offset={off}[v];"
              f"[0:a]aformat=sample_rates=48000:channel_layouts=stereo[a0];"
              f"{a1_filter};[a0][a1]acrossfade=d={a.xfade}[a]")
    else:
        fc = (f"[0:v]{norm}[v0];[1:v]{norm}[v1];"
              f"[0:a]aformat=sample_rates=48000:channel_layouts=stereo[a0];"
              f"{a1_filter};"
              f"[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a]")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", a.mid, "-i", cta,
           "-filter_complex", fc, "-map", "[v]", "-map", "[a]", *venc(w, h),
           "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", a.out]
    if subprocess.run(cmd).returncode or not _os.path.exists(a.out):
        sys.exit("cta append failed")
    ow, oh, _, odur = probe(a.out)
    print(f"[cta] ✅ {a.out}  {ow}x{oh}  {odur:.1f}s  (mid {mdur:.1f}s + outro)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
