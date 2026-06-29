"""
Caption + title helpers for finished shorts.

No external data source. A clip's title/description come from a sidecar text file next
to the video if present, otherwise from the cleaned filename. Generic only — bring your
own hashtags via env VIBE_HASHTAGS if you want them.
"""

import os
import re
from pathlib import Path

MAX_TITLE_CHARS = 95
MAX_CAPTION_CHARS = 500

# Optional default hashtags. Bring your own: export VIBE_HASHTAGS="#shorts #yourbrand".
DEFAULT_HASHTAGS = os.environ.get("VIBE_HASHTAGS", "#shorts").split()


def _sidecar_text(video_path: str) -> str | None:
    """Return the contents of a `<video>.txt` sidecar, if one exists.

    Looks for both `clip.mp4.txt` and `clip.txt` next to the video.
    """
    p = Path(video_path)
    for cand in (p.with_suffix(p.suffix + ".txt"), p.with_suffix(".txt")):
        try:
            txt = cand.read_text().strip()
            if txt:
                return txt
        except FileNotFoundError:
            continue
    return None


def _clean_filename(video_path: str) -> str:
    """Turn a filename stem into a human title: underscores/dashes -> spaces, tidy caps."""
    stem = Path(video_path).stem
    stem = re.sub(r"[_\-]+", " ", stem)
    stem = re.sub(r"\s+", " ", stem).strip()
    # Drop a leading numeric index like "03 " or "12_" leftovers.
    stem = re.sub(r"^\d{1,3}[\.\)]?\s+", "", stem)
    if stem and stem.islower():
        stem = stem.title()
    return stem or "Short"


def make_title(video_path: str) -> str:
    """Title from the sidecar's first line, else the cleaned filename."""
    side = _sidecar_text(video_path)
    if side:
        first = side.split("\n", 1)[0].strip().lstrip("#").strip()
        if len(first) >= 3:
            return first[:MAX_TITLE_CHARS]
    return _clean_filename(video_path)[:MAX_TITLE_CHARS]


def make_caption(video_path: str, title: str | None = None) -> str:
    """Build a post description.

    If the sidecar has more than one line, use its full body as the caption. Otherwise
    use the title. Append default hashtags (if any) when they aren't already present.
    """
    title = title or make_title(video_path)
    side = _sidecar_text(video_path)

    if side and "\n" in side.strip():
        body = side.strip()
    else:
        body = title

    tags = " ".join(t for t in DEFAULT_HASHTAGS if t and t.lower() not in body.lower())
    caption = body if not tags else f"{body}\n\n{tags}"
    return caption[:MAX_CAPTION_CHARS]


if __name__ == "__main__":
    import sys
    vp = sys.argv[1] if len(sys.argv) > 1 else "Some_Cool_Clip_01.mp4"
    print("Title:  ", make_title(vp))
    print("Caption:", repr(make_caption(vp)))
