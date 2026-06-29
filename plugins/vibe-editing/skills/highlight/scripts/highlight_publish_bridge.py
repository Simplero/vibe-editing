#!/usr/bin/env python3
"""
highlight_publish_bridge.py — OPTIONAL auto-upload (normally you upload manually).

Takes a finished mid (.mp4) and uploads it as a PRIVATE draft to YOUR OWN YouTube channel via
the YouTube Data API v3, using the SAME OAuth as highlight_post.py (no separate login, no
browser-profile scraping). After upload, run highlight_post.py to title + schedule it.

🛑 SAFETY: uploading is irreversible-ish + public-facing. This is DRY-RUN BY DEFAULT and does
nothing without an explicit `--yes-upload` for a specific file in a specific run. A prior
"upload it" never carries to the next file.

Most people skip this and just drag the mids into YouTube Studio. It exists for batch convenience.

Usage:
  # safe preview (no upload):
  highlight_publish_bridge.py --video mid.mp4
  # actually create the private draft (explicit, per-file):
  highlight_publish_bridge.py --video mid.mp4 --yes-upload
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
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
CONFIG_DIR = _os.path.join(VIBE_ROOT, "config")
# ── end bootstrap ──
import argparse, json, subprocess
from datetime import datetime, timezone

DEFAULT_SECRET = _os.path.join(CONFIG_DIR, "youtube_client_secret.json")
DEFAULT_TOKEN = _os.path.join(CONFIG_DIR, "youtube_token.json")
LOG = _os.path.join(VIBE_ROOT, "skills", "highlight", "workspace", "bridge_log.jsonl")


def probe(path):
    out = subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height", "-show_entries", "format=duration",
        "-of", "json", path]).decode()
    j = json.loads(out); st = j["streams"][0]
    return int(st["width"]), int(st["height"]), float(j["format"]["duration"])


def preflight(video):
    if not _os.path.exists(video):
        _sys.exit(f"no such file: {video}")
    w, h, d = probe(video)
    ok_aspect = abs(w / h - 16 / 9) < 0.06
    print(f"[preflight] {video}")
    print(f"            {w}x{h}  {d:.1f}s  {'✅ 16:9' if ok_aspect else '⚠️ NOT 16:9'}")
    if d < 60:
        print(f"            ⚠️ {d:.0f}s is short for a mid (sweet spot 3–10 min)")
    return w, h, d, ok_aspect


def log(rec):
    _os.makedirs(_os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a") as f:
        f.write(json.dumps(rec) + "\n")


def upload_private(video, title, client_secret, token_path):
    """Resumable upload as a PRIVATE draft via the YouTube Data API (recipient's own OAuth)."""
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
    except ImportError:
        _sys.exit("pip install google-api-python-client google-auth-oauthlib")
    SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
    creds = None
    if _os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not _os.path.exists(client_secret):
                _sys.exit(f"Missing OAuth client secret at {client_secret} (see SKILL.md POST setup).")
            creds = InstalledAppFlow.from_client_secrets_file(client_secret, SCOPES).run_local_server(port=0)
        _os.makedirs(_os.path.dirname(token_path), exist_ok=True)
        open(token_path, "w").write(creds.to_json())
    svc = build("youtube", "v3", credentials=creds)
    body = {"snippet": {"title": (title or _os.path.basename(video))[:95], "categoryId": "22"},
            "status": {"privacyStatus": "private", "selfDeclaredMadeForKids": False}}
    media = MediaFileUpload(video, chunksize=-1, resumable=True)
    req = svc.videos().insert(part="snippet,status", body=body, media_body=media)
    resp = None
    while resp is None:
        status, resp = req.next_chunk()
        if status:
            print(f"  uploading… {int(status.progress()*100)}%")
    return resp.get("id")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--title", default="", help="initial draft title (highlight_post.py retitles later)")
    ap.add_argument("--client-secret", default=DEFAULT_SECRET)
    ap.add_argument("--token", default=DEFAULT_TOKEN)
    ap.add_argument("--yes-upload", action="store_true", help="REQUIRED to actually upload (else dry-run)")
    a = ap.parse_args()

    w, h, d, ok = preflight(a.video)
    plan = {"video": _os.path.abspath(a.video), "dims": f"{w}x{h}", "dur_s": round(d, 1), "is_16_9": ok}
    if not a.yes_upload:
        print("\n[DRY-RUN] would upload this as a PRIVATE draft to YOUR channel, then highlight_post.py titles+schedules it.")
        print(json.dumps(plan, indent=2))
        print("\nRe-run with --yes-upload to actually upload (explicit, per-file).")
        return
    if not ok:
        _sys.exit("refusing to upload: source is not 16:9 (mids are horizontal).")
    print("\n[UPLOAD] creating a PRIVATE draft via the YouTube Data API…")
    vid = upload_private(a.video, a.title, a.client_secret, a.token)
    rec = {"ts": datetime.now(timezone.utc).isoformat(), **plan, "video_id": vid,
           "result": "draft_created" if vid else "upload_id_unconfirmed"}
    log(rec)
    print(f"[UPLOAD] {'✅ private draft created: ' + vid if vid else '⚠️ uploaded but id unconfirmed — check Studio'}")
    print("        Now run highlight_post.py --channel-id <yours> to title + schedule it.")


if __name__ == "__main__":
    main()
