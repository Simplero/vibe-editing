"""Shared helpers for render stages."""
from __future__ import annotations

import json, subprocess
from pathlib import Path


def run(cmd, **kw):
    cmd = [str(c) for c in cmd]
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
