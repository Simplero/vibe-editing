"""mix — add background music + audio leveling (loudnorm, fades, alimiter).

Config:
    {
      "music":     "/abs/path/to/track.mp3",   # null/"" = NO music bed (voice-only loudnorm)
      "voice_lufs": -16,                       # voice loudnorm target
      "music_lufs": -30,                       # music loudnorm target (under voice)
      "fade_in":    1.0,                       # music fade-in seconds
      "fade_out":   1.5,                       # music fade-out seconds
      "limiter":    0.45                       # alimiter ceiling
    }
"""
from __future__ import annotations

from pathlib import Path

from _util import run as ff, resolve_path

VERSION = "1.2.0"  # 1.2.0: pin all audio to 48kHz (aresample) so low-rate (16kHz) sources don't
                   #        emerge from loudnorm at a wrong rate + truncated duration; voice TP -1.5
                   #        (was -7, which floored integrated loudness ~3dB under the -16 target).
# 1.1.0: music=null/"" → voice-only (no bed)


def run(work_dir, config, inputs, inputs_meta, project, manifest, out_path):
    prior = inputs[list(inputs.keys())[-1]]
    music_cfg = config.get("music")
    if not music_cfg:
        voice_lufs = config.get("voice_lufs", -16)
        limiter = config.get("limiter", 0.45)
        upstream_meta = inputs_meta.get(list(inputs_meta.keys())[-1], {}) if inputs_meta else {}
        ff(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", prior,
            "-af", f"highpass=f=80,loudnorm=I={voice_lufs}:LRA=11:TP=-1.5,"
                   f"alimiter=limit={limiter}:level=disabled",
            "-map", "0:v", "-map", "0:a",
            "-c:v", "h264_videotoolbox", "-b:v", "14M", "-tag:v", "avc1", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out_path)])
        return {"out": str(out_path), "meta": {
            "music": None, "voice_lufs": voice_lufs, "limiter": limiter,
            "fps": upstream_meta.get("fps"),
            "total_duration_s": float(upstream_meta.get("total_duration_s", 0) or 0),
        }}
    music = resolve_path(music_cfg, project) if not Path(music_cfg).is_absolute() else Path(music_cfg)
    voice_lufs = config.get("voice_lufs", -16)
    music_lufs = config.get("music_lufs", -30)
    fade_in = float(config.get("fade_in", 1.0))
    fade_out = float(config.get("fade_out", 1.5))
    limiter = config.get("limiter", 0.45)

    upstream_meta = inputs_meta.get(list(inputs_meta.keys())[-1], {}) if inputs_meta else {}
    cum = float(upstream_meta.get("total_duration_s", 0) or 0)
    afade_out_st = max(0.0, round(cum - fade_out, 2))

    fc = (f"[0:a]aresample=48000,highpass=f=80,loudnorm=I={voice_lufs}:LRA=11:TP=-1.5,aresample=48000[v];"
          f"[1:a]aresample=48000,loudnorm=I={music_lufs}:LRA=11:TP=-9,aresample=48000,"
          f"afade=t=in:st=0:d={fade_in},afade=t=out:st={afade_out_st}:d={fade_out}[m];"
          f"[v][m]amix=inputs=2:duration=first:normalize=0,alimiter=limit={limiter}:level=disabled,aresample=48000[a]")

    ff(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", prior, "-i", str(music),
        "-filter_complex", fc,
        "-map", "0:v", "-map", "[a]",
        "-c:v", "h264_videotoolbox", "-b:v", "14M", "-tag:v", "avc1", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", str(out_path)])

    return {"out": str(out_path), "meta": {
        "music": str(music),
        "voice_lufs": voice_lufs, "music_lufs": music_lufs,
        "fade_in": fade_in, "fade_out": fade_out, "limiter": limiter,
        "fps": upstream_meta.get("fps"),
        "total_duration_s": cum,
    }}
