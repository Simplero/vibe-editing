#!/usr/bin/env python3
"""
/highlight MODE C — FILL your social queue with finished 9:16 shorts.

Scans a LOCAL folder of your finished 9:16 shorts, filters them, and queues each one to
YOUR YouTube channel on a schedule via the Buffer API. Buffer needs a public media URL,
so each clip is uploaded to your own storage bucket first (skip with --video-url for a
pre-hosted clip).

White-labeled: no shared database, no view-ranking, no channel lock. Everything points at
YOUR own accounts (see config.py).

RULES baked in:
  - Source = a folder of *.mp4 (newest-first, or by filename with --order name).
  - Skips clips with no audio stream, and clips outside 10-180s.
  - Never uploads the same clip twice (local URL cache).
  - Never queues the same clip twice, ever (local posted ledger).
  - Configurable DAILY CAP (env VIBE_BUFFER_DAILY_CAP, default 10) — printed loudly.

Usage:
    python3 fill_queue.py discover                 # list your Buffer channels (find your id)
    python3 fill_queue.py slots                    # preview scheduling slots
    python3 fill_queue.py fill --dry-run           # preview what WOULD be queued
    python3 fill_queue.py fill --total 10          # queue up to 10 shorts
    python3 fill_queue.py fill --dir ~/clips       # scan a specific folder
    python3 fill_queue.py fill --video-url URL ... # queue a pre-hosted clip (skip upload)
"""

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from buffer_api import create_video_post, discover
from captions import make_caption, make_title
from config import DAILY_CAP, shorts_dir
from slots import preview_slots
from storage import upload_video

HERE = Path(__file__).resolve().parent
POSTED_LOG = HERE / "posted_log.json"     # never-post-twice ledger
URL_CACHE = HERE / "url_cache.json"        # never-upload-twice cache
API_CALL_LOG = HERE / "api_calls.json"     # daily cap counter

VIDEO_EXTS = (".mp4", ".mov", ".webm", ".m4v")
MIN_DURATION_S = 10
MAX_DURATION_S = 180


# ── State tracking ─────────────────────────────────────────────────────

def _load_json(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def load_posted() -> dict:
    """{clip_key: [ISO date strings]} — every clip we've ever queued."""
    return _load_json(POSTED_LOG)


def save_posted(posted: dict) -> None:
    POSTED_LOG.write_text(json.dumps(posted, indent=2))


def was_posted_ever(posted: dict, key: str) -> bool:
    return key in posted


def mark_posted(posted: dict, key: str) -> None:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    posted.setdefault(key, [])
    if today not in posted[key]:
        posted[key].append(today)


def load_url_cache() -> dict:
    return _load_json(URL_CACHE)


def save_url_cache(cache: dict) -> None:
    URL_CACHE.write_text(json.dumps(cache, indent=2))


# ── Daily cap ──────────────────────────────────────────────────────────

def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def get_calls_today() -> int:
    return _load_json(API_CALL_LOG).get(_today(), 0)


def increment_calls() -> None:
    calls = _load_json(API_CALL_LOG)
    calls[_today()] = calls.get(_today(), 0) + 1
    API_CALL_LOG.write_text(json.dumps(calls, indent=2))


def budget_remaining() -> int:
    return max(0, DAILY_CAP - get_calls_today())


# ── Validation ─────────────────────────────────────────────────────────

def has_audio(video_path: str) -> bool:
    """True if the file has an audio stream (via ffprobe)."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet", "-select_streams", "a",
                "-show_entries", "stream=codec_type",
                "-of", "csv=p=0", video_path,
            ],
            capture_output=True, text=True, timeout=10,
        )
        return "audio" in result.stdout
    except Exception:
        return False


def duration_s(video_path: str) -> float:
    """Clip duration in seconds (via ffprobe); 0.0 if unknown."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-show_entries", "format=duration",
                "-of", "csv=p=0", video_path,
            ],
            capture_output=True, text=True, timeout=10,
        )
        return float(result.stdout.strip() or 0.0)
    except Exception:
        return 0.0


def clip_key(video_path: str) -> str:
    """Stable identity for a clip in the ledgers — its filename stem."""
    return Path(video_path).stem


# ── Clip discovery (LOCAL FOLDER — no DB) ──────────────────────────────

def scan_clips(folder: Path, posted: dict, order: str = "mtime") -> list[dict]:
    """Find eligible *.mp4 shorts in a folder.

    Eligible = video file, has audio, duration in [10, 180]s, not queued before.
    order: 'mtime' (newest modified first, default) or 'name' (filename sort).
    """
    if not folder.exists():
        print(f"  Shorts folder does not exist: {folder}")
        return []

    files = [p for p in folder.iterdir() if p.suffix.lower() in VIDEO_EXTS]
    if order == "name":
        files.sort(key=lambda p: p.name)
    else:
        files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    clips = []
    skipped_posted = skipped_noaudio = skipped_dur = 0
    for p in files:
        key = clip_key(str(p))
        if was_posted_ever(posted, key):
            skipped_posted += 1
            continue
        dur = duration_s(str(p))
        if dur and not (MIN_DURATION_S <= dur <= MAX_DURATION_S):
            skipped_dur += 1
            continue
        if not has_audio(str(p)):
            skipped_noaudio += 1
            continue
        clips.append({
            "key": key,
            "video_path": str(p),
            "title": make_title(str(p)),
            "duration_s": round(dur, 1),
        })

    print(f"  Found {len(files)} video file(s) in {folder}")
    print(f"  Skipped: {skipped_posted} already-queued, "
          f"{skipped_noaudio} no audio, {skipped_dur} out of {MIN_DURATION_S}-{MAX_DURATION_S}s")
    return clips


# ── Main fill ──────────────────────────────────────────────────────────

def fill(folder: Path, total: int, dry_run: bool = False, order: str = "mtime",
         video_url: str | None = None) -> None:
    posted = load_posted()
    url_cache = load_url_cache()
    remaining = budget_remaining()

    print("=" * 56)
    print(f"  DAILY CAP: {DAILY_CAP} posts/day  "
          f"({remaining} remaining today)   [env VIBE_BUFFER_DAILY_CAP]")
    print("=" * 56)
    print(f"Source folder : {folder}")
    print(f"Clips queued before (ledger): {len(posted)}")
    print(f"URLs cached   : {len(url_cache)}")
    print(f"Target        : {total} clip(s)")

    if remaining <= 0 and not dry_run:
        print(f"\nDAILY CAP REACHED ({DAILY_CAP} posts). Try again tomorrow, "
              f"or raise VIBE_BUFFER_DAILY_CAP.")
        return

    if not dry_run and total > remaining:
        print(f"Capping target to {remaining} (daily cap).")
        total = remaining

    print()
    clips = scan_clips(folder, posted, order=order)
    print(f"Eligible clips: {len(clips)}")
    if not clips:
        print("No eligible clips to queue.")
        return

    if len(clips) < total:
        print(f"NOTE: only {len(clips)} eligible (target {total}).")
        total = len(clips)

    queued = failed = consecutive_fails = 0

    for i, clip in enumerate(clips[:total], 1):
        key = clip["key"]
        title = clip["title"]
        caption = make_caption(clip["video_path"], title)

        print(f"\n[{i}/{total}] {key}  ({clip['duration_s']}s)")
        print(f"  Title  : {title[:70]}")
        print(f"  Caption: {caption.splitlines()[0][:70]}")

        if dry_run:
            print("  -> DRY RUN (nothing uploaded or queued)")
            queued += 1
            continue

        try:
            # 1. Public URL — pre-hosted (--video-url), cached, or upload now.
            if video_url:
                clip_url = video_url
                print("  Upload : skipped (--video-url)")
            elif key in url_cache:
                clip_url = url_cache[key]
                print("  Upload : cached")
            else:
                clip_url = upload_video(clip["video_path"])
                url_cache[key] = clip_url
                save_url_cache(url_cache)

            # 2. Queue to Buffer (rate-limit retry).
            post = None
            for attempt in range(3):
                try:
                    post = create_video_post(
                        video_url=clip_url,
                        text=caption,
                        title=title,
                        privacy="public",
                    )
                    break
                except RuntimeError as api_err:
                    if "429" in str(api_err) or "RATE_LIMIT" in str(api_err).upper():
                        wait = 65 * (attempt + 1)
                        print(f"  Rate limited — waiting {wait}s (attempt {attempt + 1}/3)")
                        time.sleep(wait)
                    else:
                        raise
            if post is None:
                raise RuntimeError("Rate limit persisted after 3 retries")

            mark_posted(posted, key)
            save_posted(posted)
            increment_calls()
            queued += 1
            consecutive_fails = 0
            print(f"  -> Queued: {post['id']} for {post.get('dueAt', 'next slot')}")

            if budget_remaining() <= 0:
                print(f"\n  DAILY CAP REACHED ({DAILY_CAP}). Stopping.")
                break

            # Pace: 2s between posts, 90s pause every 25.
            if queued % 25 == 0:
                print("\n  Pacing pause (25-post batch)... 90s")
                time.sleep(90)
            else:
                time.sleep(2)

        except Exception as e:
            failed += 1
            consecutive_fails += 1
            print(f"  -> FAILED: {e}")
            if consecutive_fails >= 10:
                print("\n10 consecutive failures — stopping.")
                break
            time.sleep(5)

    save_posted(posted)
    save_url_cache(url_cache)

    print(f"\n{'=' * 50}")
    print(f"DONE: {queued} queued, {failed} failed")
    print(f"Total unique clips queued (all time): {len(posted)}")


# ── CLI ────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="MODE C — fill your social queue with finished 9:16 shorts."
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("discover", help="List your Buffer channels (find YOUR channel id)")
    slots_p = sub.add_parser("slots", help="Preview scheduling slots")
    slots_p.add_argument("-n", "--count", type=int, default=24)

    f_p = sub.add_parser("fill", help="Queue shorts from a folder")
    f_p.add_argument("--dir", default=None,
                     help="Folder of finished 9:16 shorts "
                          "(else env VIBE_SHORTS_DIR, else the kit deliver folder)")
    f_p.add_argument("--total", type=int, default=DAILY_CAP,
                     help=f"How many to queue (default = daily cap {DAILY_CAP})")
    f_p.add_argument("--order", choices=["mtime", "name"], default="mtime",
                     help="newest-modified first (default) or filename order")
    f_p.add_argument("--video-url", default=None,
                     help="Pre-hosted URL to queue (skips upload; for a single clip)")
    f_p.add_argument("--dry-run", action="store_true",
                     help="Preview only — no upload, no queue, no ledger writes")

    args = parser.parse_args()

    if args.command == "discover":
        discover()
    elif args.command == "slots":
        preview_slots(args.count)
    elif args.command == "fill":
        folder = shorts_dir(args.dir)
        fill(folder, total=args.total, dry_run=args.dry_run,
             order=args.order, video_url=args.video_url)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
