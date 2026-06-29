"""
Upload a video to YOUR object storage and return its public URL.

Buffer requires a publicly reachable media URL. This uploads each clip to your own
bucket (Supabase Storage by default — any S3-style public bucket works) and returns
the public URL. Nothing here points at any shared/managed account: the project URL,
key, and bucket all come from config (env SUPABASE_URL / SUPABASE_KEY / SUPABASE_BUCKET
or ~/.config/supabase/).

To skip uploading for a pre-hosted clip, pass its URL via fill_queue's --video-url.
"""

import hashlib
import mimetypes
import sys
from pathlib import Path

import requests

from config import STORAGE_PREFIX, storage_bucket, storage_key, storage_url


def upload_video(local_path: str, object_name: str | None = None) -> str:
    """Upload a video to your storage bucket, return the public URL."""
    p = Path(local_path)
    if not p.exists():
        raise FileNotFoundError(f"Video not found: {local_path}")

    if object_name is None:
        h = hashlib.md5(p.read_bytes()[:1024 * 64]).hexdigest()[:8]
        object_name = f"{h}_{p.name}"

    base = storage_url()
    bucket = storage_bucket()
    mime = mimetypes.guess_type(p.name)[0] or "video/mp4"
    storage_path = f"{STORAGE_PREFIX}/{object_name}"
    upload_endpoint = f"{base}/storage/v1/object/{bucket}/{storage_path}"

    key = storage_key()
    headers = {
        "Authorization": f"Bearer {key}",
        "apikey": key,
        "Content-Type": mime,
        "x-upsert": "true",
    }

    print(f"Uploading {p.name} ({p.stat().st_size / 1024 / 1024:.1f} MB) -> storage...")
    with open(p, "rb") as f:
        resp = requests.post(upload_endpoint, headers=headers, data=f)

    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Upload failed ({resp.status_code}): {resp.text}")

    public_url = f"{base}/storage/v1/object/public/{bucket}/{storage_path}"
    print(f"Uploaded -> {public_url}")
    return public_url


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python storage.py <video_path>")
        sys.exit(1)
    url = upload_video(sys.argv[1])
    print(f"\nPublic URL:\n{url}")
