#!/usr/bin/env python3
"""audio-enhance — clean voice audio via Auphonic (denoise + leveler [+ loudness]),
the SAME engine the content-pipeline uses ("Voice Cleaner"). Input audio OR video;
outputs an enhanced 48k stereo WAV. Passthrough-copies if no API key is present.

Usage: enhance.py <input> --out <out.wav> [--loudness -16 | --no-loudness]
                   [--no-denoise] [--no-leveler] [--timeout 600]
Key: AUPHONIC_API_KEY env, else <plugin>/config/keys.env.
"""
import sys, os, json, time, subprocess, tempfile, argparse
from pathlib import Path
import requests

API = "https://auphonic.com/api"

def load_env(name):
    v = os.environ.get(name)
    if v: return v
    for p in [Path(__file__).resolve()] + list(Path(__file__).resolve().parents):
        f = p / "config" / "keys.env"
        if f.exists():
            for line in f.read_text().splitlines():
                if line.strip().startswith(name + "="):
                    val = line.split("=", 1)[1].strip()
                    if val and "PASTE" not in val: return val
    return None

def load_key(): return load_env("AUPHONIC_API_KEY")

def _config_dir():
    for p in Path(__file__).resolve().parents:
        if (p / "config" / "keys.env").exists(): return p / "config"
    return Path("/tmp")

def notify_telegram(msg, dedup_hours=6):
    """Alert Calvin on Telegram (e.g. Auphonic out of credits). Deduped so it can't spam."""
    marker = _config_dir() / ".auphonic_alert"
    try:
        if marker.exists() and time.time() - float(marker.read_text().strip()) < dedup_hours * 3600:
            print("[enhance] telegram alert suppressed (deduped)", file=sys.stderr); return
    except Exception: pass
    tok, chat = load_env("TELEGRAM_BOT_TOKEN"), load_env("TELEGRAM_CHAT_ID")
    if not tok or not chat:
        print("[enhance] telegram not configured; no alert sent", file=sys.stderr); return
    try:
        requests.post(f"https://api.telegram.org/bot{tok}/sendMessage",
                      data={"chat_id": chat, "text": msg, "disable_web_page_preview": True}, timeout=15)
        marker.write_text(str(time.time()))
        print("[enhance] telegram alert sent", file=sys.stderr)
    except Exception as ex:
        print(f"[enhance] telegram alert failed: {ex}", file=sys.stderr)

def sh(cmd): subprocess.run(cmd, check=True)

def local_enhance(src, out, loudness, denoise, leveler):
    """Free offline fallback (no Auphonic credits/key): ffmpeg voice-cleanup chain —
    highpass rumble, FFT denoise, compressor (leveler), loudnorm (loudness)."""
    chain = ["highpass=f=80"]
    if denoise: chain.append("afftdn=nf=-25")
    if leveler: chain.append("acompressor=threshold=-20dB:ratio=3:attack=5:release=120:makeup=2")
    if loudness is not None: chain.append(f"loudnorm=I={int(round(loudness))}:TP=-1.5:LRA=11")
    else: chain.append("dynaudnorm=f=200:g=5")
    sh(["ffmpeg", "-nostdin", "-v", "error", "-i", src, "-af", ",".join(chain),
        "-ac", "2", "-ar", "48000", out, "-y"])
    print("[enhance] used LOCAL ffmpeg chain: " + ",".join(chain), file=sys.stderr)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input"); ap.add_argument("--out", required=True)
    ap.add_argument("--loudness", type=float, default=-16.0)
    ap.add_argument("--no-loudness", action="store_true")
    ap.add_argument("--no-denoise", action="store_true")
    ap.add_argument("--no-leveler", action="store_true")
    ap.add_argument("--timeout", type=int, default=600)
    a = ap.parse_args()
    key = load_key()
    # extract audio to wav (Auphonic operates on audio)
    src = tempfile.mktemp(suffix=".wav")
    sh(["ffmpeg", "-nostdin", "-v", "error", "-i", a.input, "-vn", "-ac", "2",
        "-ar", "48000", "-c:a", "pcm_s16le", src, "-y"])
    loud = None if a.no_loudness else a.loudness
    denoise = not a.no_denoise; leveler = not a.no_leveler
    try:
        if not key:
            raise RuntimeError("no AUPHONIC_API_KEY")
        H = {"Authorization": f"Bearer {key}"}
        algos = {"denoise": denoise, "leveler": leveler, "loudness": not a.no_loudness}
        if not a.no_loudness: algos["loudnesstarget"] = int(round(a.loudness))  # Auphonic wants an int
        body = {"metadata": {"title": "vibe-editing enhance"},
                "output_files": [{"format": "mp3", "bitrate": "192"}], "algorithms": algos}
        r = requests.post(f"{API}/productions.json", headers={**H, "Content-Type": "application/json"},
                          data=json.dumps(body), timeout=60); r.raise_for_status()
        uuid = r.json()["data"]["uuid"]
        print(f"[enhance] auphonic production {uuid} algos={algos}", file=sys.stderr)
        with open(src, "rb") as f:
            r = requests.post(f"{API}/production/{uuid}/upload.json", headers=H,
                              files={"input_file": (os.path.basename(src), f)}, timeout=300)
        r.raise_for_status()
        r = requests.post(f"{API}/production/{uuid}/start.json", headers=H, timeout=60); r.raise_for_status()
        t0 = time.time(); dl = None
        while time.time() - t0 < a.timeout:
            r = requests.get(f"{API}/production/{uuid}.json", headers=H, timeout=60); r.raise_for_status()
            d = r.json()["data"]
            if d.get("error_message"): raise RuntimeError("Auphonic: " + str(d["error_message"]))
            got = [o for o in d.get("output_files", []) if o.get("download_url")]
            if got and d.get("status") == 3:
                dl = got[0]["download_url"]; break
            print(f"[enhance] status {d.get('status')} {d.get('status_string')} ({int(time.time()-t0)}s)", file=sys.stderr)
            time.sleep(8)
        if not dl: raise RuntimeError("Auphonic timed out / no output")
        if dl.startswith("/"): dl = "https://auphonic.com" + dl
        r = requests.get(dl, headers=H, timeout=300); r.raise_for_status()
        raw = tempfile.mktemp(suffix=".mp3"); open(raw, "wb").write(r.content)
        sh(["ffmpeg", "-nostdin", "-v", "error", "-i", raw, "-ac", "2", "-ar", "48000", a.out, "-y"])
        print(f"[enhance] used AUPHONIC -> {a.out}", file=sys.stderr)
    except Exception as e:
        emsg = str(e)
        if "credit" in emsg.lower():
            notify_telegram("Auphonic is OUT OF CREDITS — vibe-editing audio enhancement fell back "
                            "to the free local voice cleaner for this clip. Add credits to restore "
                            "studio-grade cleanup: https://auphonic.com/pricing")
        print(f"[enhance] Auphonic unavailable ({e}); using local fallback", file=sys.stderr)
        local_enhance(src, a.out, loud, denoise, leveler)

if __name__ == "__main__": main()
