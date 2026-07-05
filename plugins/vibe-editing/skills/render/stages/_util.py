"""Shared helpers for render stages."""
from __future__ import annotations

import json, subprocess
from pathlib import Path


import shutil as _shutil

# The stages hard-code Apple's h264_videotoolbox encoder. On a non-macOS host that encoder
# doesn't exist, so transparently fall back to libx264 (present everywhere) with an equivalent
# quality/bitrate setup. Central swap here keeps every stage identical on Mac and Linux.
_HAS_VTB = None
def _has_vtb():
    global _HAS_VTB
    if _HAS_VTB is None:
        try:
            out = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"],
                                 capture_output=True, text=True)
            _HAS_VTB = "h264_videotoolbox" in out.stdout
        except Exception:
            _HAS_VTB = False
    return _HAS_VTB


def _swap_encoder(cmd):
    if _has_vtb() or "h264_videotoolbox" not in cmd:
        return cmd
    out = []
    i = 0
    while i < len(cmd):
        tok = cmd[i]
        if tok == "h264_videotoolbox":
            out.append("libx264")
        elif tok == "-b:v":
            # libx264: prefer CRF-based quality over ABR; drop the videotoolbox bitrate pair.
            i += 2
            continue
        elif tok == "-tag:v":
            i += 2
            continue
        else:
            out.append(tok)
        i += 1
    # Inject libx264 quality knobs right after the codec token.
    if "libx264" in out:
        j = out.index("libx264")
        out[j+1:j+1] = ["-preset", "medium", "-crf", "17"]
    return out


def run(cmd, **kw):
    cmd = _swap_encoder([str(c) for c in cmd])
    print("  $", " ".join(cmd[:8]) + (" ..." if len(cmd) > 8 else ""), flush=True)
    return subprocess.run(cmd, check=True, **kw)


def resolve_path(p: str | Path, project: Path) -> Path:
    """Resolve a config path. Absolute -> as-is. Relative -> under project root."""
    p = Path(p)
    return p if p.is_absolute() else (project / p)


def ffprobe_duration(p: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(p)], capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def ffprobe_fps(p: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                          "-show_entries", "stream=r_frame_rate", "-of", "csv=p=0", str(p)],
                         capture_output=True, text=True, check=True)
    num, den = out.stdout.strip().split("/")
    return float(num) / float(den)
