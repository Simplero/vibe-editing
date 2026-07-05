"""enhance — clean the VOICE via the audio-enhance skill (Auphonic, with a free local
ffmpeg fallback) right before the mix stage. Passthrough if disabled.

Config (manifest.stages.enhance):
    { "enabled": true,        # false => passthrough copy
      "loudness": null,       # null => let mix do final loudnorm (recommended); or a LUFS number
      "denoise": true,        # noise reduction
      "leveler": true }       # even out level dynamics
"""
from __future__ import annotations
import sys, subprocess, tempfile
from pathlib import Path
from _util import run as ff

VERSION = "1.0.0"

def _skill():
    for p in Path(__file__).resolve().parents:
        c = p / "skills" / "audio-enhance" / "scripts" / "enhance.py"
        if c.exists(): return str(c)
    return None

def run(work_dir, config, inputs, inputs_meta, project, manifest, out_path):
    prior = inputs[list(inputs.keys())[-1]]
    script = _skill()
    if not config.get("enabled", True) or not script:
        ff(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(prior), "-c", "copy", str(out_path)])
        return {"out": str(out_path), "meta": {"enhanced": False}}
    enh = tempfile.mktemp(suffix=".wav")
    cmd = [sys.executable, script, str(prior), "--out", enh]
    loud = config.get("loudness", None)
    cmd += ["--no-loudness"] if loud is None else ["--loudness", str(loud)]
    if config.get("denoise") is False: cmd.append("--no-denoise")
    if config.get("leveler") is False: cmd.append("--no-leveler")
    try:
        subprocess.run(cmd, check=True)
        ff(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(prior), "-i", enh,
            "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-shortest", str(out_path)])
        return {"out": str(out_path), "meta": {"enhanced": True}}
    except Exception as e:
        ff(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(prior), "-c", "copy", str(out_path)])
        return {"out": str(out_path), "meta": {"enhanced": False, "error": str(e)}}
