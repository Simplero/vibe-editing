#!/usr/bin/env python3
"""notify_clip.py — send a finished short to Telegram as the actual VIDEO (+ caption + link).
Telegram bots cap uploads at 50MB, so this transcodes to a phone-friendly 1080x1920 (~15-20MB).
If it's still >49MB, it sends the caption+link only. Reads TELEGRAM_* from config/keys.env.
Usage: notify_clip.py <video.mp4> --title "..." [--link URL]
"""
import sys, os, json, subprocess, tempfile, argparse
from pathlib import Path
import requests

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

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video"); ap.add_argument("--title", default="New short")
    ap.add_argument("--link", default=None)
    a = ap.parse_args()
    tok, chat = load_env("TELEGRAM_BOT_TOKEN"), load_env("TELEGRAM_CHAT_ID")
    if not tok or not chat:
        print("[notify] telegram not configured", file=sys.stderr); return
    cap = a.title + (f"\n{a.link}" if a.link else "")
    tg = tempfile.mktemp(suffix=".mp4")
    # aspect-aware downscale so BOTH 9:16 shorts and 16:9 mids compress correctly:
    # long edge -> 1920 (portrait scales to 1080x1920, landscape to 1920x1080).
    scale = "scale='if(gt(a,1),1920,-2)':'if(gt(a,1),-2,1920)':flags=lanczos"
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", a.video,
        "-vf", scale, "-c:v", "libx264", "-preset", "veryfast",
        "-b:v", "3500k", "-maxrate", "4200k", "-bufsize", "6000k", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", tg, "-y"], check=True)
    size = os.path.getsize(tg)
    pr = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height", "-show_entries", "format=duration",
        "-of", "json", tg], capture_output=True, text=True)
    meta = json.loads(pr.stdout); st = meta["streams"][0]; dur = float(meta["format"]["duration"])
    if size <= 49 * 1024 * 1024:
        with open(tg, "rb") as f:
            r = requests.post(f"https://api.telegram.org/bot{tok}/sendVideo",
                data={"chat_id": chat, "caption": cap, "supports_streaming": "true",
                      "width": st["width"], "height": st["height"], "duration": int(dur)},
                files={"video": (os.path.basename(a.video), f, "video/mp4")}, timeout=600)
        ok = r.json().get("ok")
        print(f"[notify] sendVideo ok={ok} ({size//1048576}MB)", file=sys.stderr)
        if not ok:
            print(r.text[:300], file=sys.stderr)
            requests.post(f"https://api.telegram.org/bot{tok}/sendMessage", data={"chat_id": chat, "text": cap})
    else:
        print(f"[notify] {size//1048576}MB >49 — link only", file=sys.stderr)
        requests.post(f"https://api.telegram.org/bot{tok}/sendMessage", data={"chat_id": chat, "text": cap})
    os.remove(tg)

if __name__ == "__main__": main()
