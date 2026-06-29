#!/usr/bin/env python3
"""export_premiere_srt.py — convert a spice subs_text.ass into Premiere-importable SRT(s).

Single-speaker output (default):
    One .srt with bold/italic/color markup per word.

Split-speaker output (--split, recommended for Q&A / hotline):
    Two files — <stem>_host.srt and <stem>_guest.srt — one per speaker.
    the reference editor drags both into Premiere as separate Caption tracks and applies
    his "white Speaker" preset to host and "yellow guest" preset to guest.
    No hunting, no manual recoloring.

Usage:
    python3 export_premiere_srt.py <subs_text.ass> [--out captions.srt] [--split]
"""
from __future__ import annotations
import argparse, re, sys
from pathlib import Path


def ass_time_to_srt(t: str) -> str:
    """'H:MM:SS.cc' → 'HH:MM:SS,mmm'"""
    h, m, rest = t.split(":")
    s, cs = rest.split(".")
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int(cs) * 10:03d}"


def parse_color(color_str: str) -> str:
    """ASS &HAABBGGRR& hex → RRGGBB string."""
    c = color_str.upper()
    if len(c) == 8:   # AABBGGRR
        return c[6:8] + c[4:6] + c[2:4]
    if len(c) == 6:   # BBGGRR
        return c[4:6] + c[2:4] + c[0:2]
    return "FFFFFF"


def parse_word_tokens(text: str) -> list[tuple[str, bool, bool, str]]:
    """Parse ASS inline text → (word, is_bold, is_italic, rrggbb) tuples."""
    tokens = []
    for m in re.finditer(r"\{([^}]*)\}([^{]*)", text):
        tags, word_text = m.group(1), m.group(2).strip()
        if not word_text:
            continue
        fn_m   = re.search(r"\\fn([^\\}]+)", tags)
        font   = fn_m.group(1) if fn_m else "Montserrat Medium"
        fax_m  = re.search(r"\\fax(-?[\d.]+)", tags)
        fax    = float(fax_m.group(1)) if fax_m else 0.0
        col_m  = re.search(r"\\1c&H([0-9A-Fa-f]{6,8})&", tags)
        rrggbb = parse_color(col_m.group(1)) if col_m else "FFFFFF"
        tokens.append((word_text, any(w in font for w in ("Bold", "Extrabold", "Black")),
                       abs(fax) > 0.05, rrggbb))
    return tokens


def format_token(word: str, is_bold: bool, is_italic: bool, rrggbb: str,
                 strip_color: bool = False) -> str:
    text = word
    if is_bold:
        text = f"<b>{text}</b>"
    if is_italic:
        text = f"<i>{text}</i>"
    if not strip_color and rrggbb.upper() != "FFFFFF":
        text = f'<font color="#{rrggbb.upper()}">{text}</font>'
    return text


def cue_is_guest(tokens: list[tuple]) -> bool:
    """True if the majority of words in this cue are guest-colored (non-white)."""
    colored = sum(1 for _, _, _, rgb in tokens if rgb.upper() != "FFFFFF")
    return colored > len(tokens) / 2


def load_cues(ass_path: Path) -> list[tuple[str, str, list]]:
    cues = []
    for line in ass_path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.startswith("Dialogue:"):
            continue
        parts = line.split(",", 9)
        if len(parts) < 10:
            continue
        raw = re.sub(r"^\{[^}]*\}", "", parts[9])
        tokens = parse_word_tokens(raw)
        if tokens:
            cues.append((parts[1], parts[2], tokens))
    return cues


def write_srt(cues: list[tuple], out: Path, strip_color: bool = False) -> int:
    blocks = []
    for i, (st, en, tokens) in enumerate(cues, 1):
        text = " ".join(format_token(*t, strip_color=strip_color) for t in tokens)
        blocks.append(f"{i}\n{ass_time_to_srt(st)} --> {ass_time_to_srt(en)}\n{text}")
    out.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")
    return len(blocks)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ass", help="subs_text.ass from generate_spice")
    ap.add_argument("--out", help="output path (single-speaker mode)")
    ap.add_argument("--split", action="store_true",
                    help="Split into _host.srt + _guest.srt (Q&A / hotline)")
    a = ap.parse_args()

    ass_path = Path(a.ass).expanduser()
    if not ass_path.exists():
        sys.exit(f"ERROR: not found: {ass_path}")

    cues = load_cues(ass_path)
    if not cues:
        sys.exit(f"ERROR: no caption cues in {ass_path.name}")

    has_guest = any(cue_is_guest(toks) for _, _, toks in cues)

    if a.split and has_guest:
        stem = ass_path.with_suffix("")
        host_path  = Path(str(stem) + "_host.srt")
        guest_path = Path(str(stem) + "_guest.srt")
        host_cues  = [(st, en, t) for st, en, t in cues if not cue_is_guest(t)]
        guest_cues = [(st, en, t) for st, en, t in cues if     cue_is_guest(t)]
        n_host  = write_srt(host_cues,  host_path,  strip_color=True)
        n_guest = write_srt(guest_cues, guest_path, strip_color=True)
        print(f"export_premiere_srt: {n_host} host cues → {host_path.name}")
        print(f"export_premiere_srt: {n_guest} guest cues → {guest_path.name}")
    else:
        out = Path(a.out).expanduser() if a.out else ass_path.with_suffix(".srt")
        n = write_srt(cues, out)
        print(f"export_premiere_srt: {n} cues → {out.name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
