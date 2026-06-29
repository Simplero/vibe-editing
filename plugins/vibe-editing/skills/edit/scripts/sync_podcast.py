#!/usr/bin/env python3
"""sync.py --config <multicam_config.json>
Robust multicam audio sync via ENERGY-ENVELOPE cross-correlation.

For each episode in the config, MASTER = wide cam (Δ=0). For every other source (host/guest
cams + host/guest lavs) compute Δ where source_time = wide_time + Δ  ⇒  wide_time = source_time - Δ.

Envelope (RMS @100 Hz, log+znorm) aligns speech rhythm across very different mics (close lav
vs room-scratch on a cam) far better than raw-sample xcorr — that's why this is the locked sync
method. A lock-quality flag is printed: peak/median (sharp) — anything <8 is suspicious; verify
manually before cutting.

Writes <project_root>/10_WORK/sync_map.json keyed by episode.

Schema (per episode):
  "Ep01": {"wide": 0.0, "host_cam": ..., "guest_cam": ..., "host_wav": ..., "guest_wav": ...}

WAV-TIME CONVENTION used downstream:
  - cut timestamps (t0/t1) are in HOST_WAV time (the lav's transcript was time-base for diarize)
  - wide-time at t0  = t0 - Δ_host_wav
  - host_cam seek    = (t0 - Δ_host_wav) + Δ_host_cam
  - guest_wav seek   = (t0 - Δ_host_wav) + Δ_guest_wav   (only diverges when lavs were recorded on
                                                          separate recorders; same-recorder lavs share Δ)
"""
import argparse, json, subprocess
from pathlib import Path
import numpy as np

SR, FR = 8000, 100   # audio 8 kHz; envelope 100 Hz (10 ms frames)


def envelope(path):
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-vn", "-i", str(path),
         "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
        capture_output=True).stdout
    a = np.frombuffer(raw, dtype=np.float32)
    n = SR // FR
    m = len(a) // n
    env = np.sqrt((a[:m * n].reshape(m, n) ** 2).mean(axis=1) + 1e-9)   # RMS per 10 ms → 100 Hz
    env = np.log1p(env * 50.0)                                          # log-compress
    return (env - env.mean()) / (env.std() + 1e-9)


def lag_seconds(wide, src):
    """Δ such that source_time = wide_time + Δ."""
    nf = 1 << int(np.ceil(np.log2(len(wide) + len(src))))
    C = np.fft.irfft(np.fft.rfft(src, nf) * np.conj(np.fft.rfft(wide, nf)), nf)
    i = int(np.argmax(C))
    sharp = float(C.max() / (np.median(np.abs(C)) + 1e-9))              # peak/median = lock quality
    if i > nf // 2:
        i -= nf
    return i / FR, sharp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, type=Path)
    args = ap.parse_args()
    cfg = json.loads(args.config.read_text())
    root = Path(cfg["project_root"]).expanduser()
    src_dir = root            # config episode paths are relative to project_root
    out_dir = root / "10_WORK"
    out_dir.mkdir(parents=True, exist_ok=True)

    eps = cfg["episodes"]
    out = {}
    for ep, files in eps.items():
        if "wide" not in files:
            print(f"⚠ {ep}: no 'wide' camera in config; skipping"); continue
        print(f"\n=== {ep} ===")
        wide_env = envelope(src_dir / files["wide"])
        out[ep] = {"wide": 0.0}
        for name, rel in files.items():
            if name == "wide":
                continue
            d, sharp = lag_seconds(wide_env, envelope(src_dir / rel))
            out[ep][name] = round(d, 3)
            flag = "OK" if sharp > 8 else "⚠ LOW (verify)"
            print(f"  {name:12s} Δ={d:+9.3f}s  sharp={sharp:6.1f}  {flag}")

    sync_path = out_dir / "sync_map.json"
    sync_path.write_text(json.dumps(out, indent=2))
    print(f"\nwrote {sync_path}")


if __name__ == "__main__":
    main()
