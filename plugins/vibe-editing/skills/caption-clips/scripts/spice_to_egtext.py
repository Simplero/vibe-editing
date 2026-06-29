#!/usr/bin/env python3
"""spice_to_egtext.py — spice subs_text.ass  ->  cues.json (per-word style RUNS).

The SINK for the Premiere Essential-Graphics caption path. It does NOT change the
source pipeline; it re-serializes the per-word styling generate_spice.py already
emits in the .ass into a flat JSON the ExtendScript host can consume without an ASS
parser in ES3.

Each cue -> one EG text clip; each word -> one style run carrying the FULL spice axes:
  font (Montserrat Medium/Bold/Extrabold/Black), sizePct (\\fscx, 100=base),
  italic (\\fax shear flag), colorRGB (white host / gold guest).

Output:
  { "meta": { base_size_frac, y_frac, colors, font_default, source },
    "cues": [ { start_s, end_s, track:"host"|"guest", text, runs:[
                 { text, font, sizePct, colorRGB, italic } ] } ] }

Usage:
  python3 spice_to_egtext.py <subs_text.ass> --out cues.json [--ref-height 2160]
"""
from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path

# reuse the proven .ass color + line parsing from the SRT exporter
sys.path.insert(0, str(Path(__file__).resolve().parent))
from export_premiere_srt import parse_color  # noqa: E402

SKILL = Path(__file__).resolve().parent.parent
PRESET = SKILL / "presets" / "spice.json"


def ass_time_to_seconds(t: str) -> float:
    """'H:MM:SS.cc' -> float seconds."""
    h, m, rest = t.split(":")
    s, cs = rest.split(".")
    return int(h) * 3600 + int(m) * 60 + int(s) + int(cs) / 100.0


def parse_runs(text: str) -> list[dict]:
    """ASS inline text -> per-word run dicts with the FULL style axes."""
    runs = []
    for m in re.finditer(r"\{([^}]*)\}([^{]*)", text):
        tags, word = m.group(1), m.group(2).strip()
        if not word:
            continue
        fn = re.search(r"\\fn([^\\}]+)", tags)
        font = fn.group(1).strip() if fn else "Montserrat Medium"
        sx = re.search(r"\\fscx(-?[\d.]+)", tags)
        size_pct = round(float(sx.group(1))) if sx else 100
        fax = re.search(r"\\fax(-?[\d.]+)", tags)
        italic = bool(fax and abs(float(fax.group(1))) > 0.05)
        col = re.search(r"\\1c&H([0-9A-Fa-f]{6,8})&", tags)
        rgb = parse_color(col.group(1)) if col else "FFFFFF"
        runs.append({"text": word, "font": font, "sizePct": size_pct,
                     "colorRGB": rgb.upper(), "italic": italic})
    return runs


def cue_track(runs: list[dict]) -> str:
    """host = majority white; guest = majority colored (gold)."""
    colored = sum(1 for r in runs if r["colorRGB"] != "FFFFFF")
    return "guest" if colored > len(runs) / 2 else "host"


def load_cues(ass_path: Path) -> list[dict]:
    cues = []
    for line in ass_path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.startswith("Dialogue:"):
            continue
        parts = line.split(",", 9)
        if len(parts) < 10:
            continue
        raw = re.sub(r"^\{[^}]*\}", "", parts[9])   # drop the leading line-level override block
        runs = parse_runs(raw)
        if not runs:
            continue
        cues.append({
            "start_s": round(ass_time_to_seconds(parts[1]), 3),
            "end_s": round(ass_time_to_seconds(parts[2]), 3),
            "track": cue_track(runs),
            "text": " ".join(r["text"] for r in runs),
            "runs": runs,
        })
    return cues


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("ass")
    ap.add_argument("--out", required=True)
    ap.add_argument("--ref-height", type=int, default=2160,
                    help="reference frame height the preset font_size_px was calibrated at")
    a = ap.parse_args()

    ass_path = Path(a.ass).expanduser()
    if not ass_path.exists():
        sys.exit(f"ERROR: not found: {ass_path}")

    preset = json.loads(PRESET.read_text()) if PRESET.exists() else {}
    font_px = preset.get("font_size_px", 150)
    colors = preset.get("colors", {"speaker": "FFFFFF", "guest": "FECB00"})
    y_frac = (preset.get("y", 50) or 50) / 100.0 if isinstance(preset.get("y", 50), (int, float)) else 0.50

    cues = load_cues(ass_path)
    if not cues:
        sys.exit(f"ERROR: no cues in {ass_path.name}")

    out = {
        "meta": {
            "base_size_frac": round(font_px / a.ref_height, 5),   # font px as a fraction of frame height
            "y_frac": y_frac,
            "colors": {k: v.upper() for k, v in colors.items()},
            "font_default": "Montserrat Medium",
            "source": str(ass_path),
            "n_cues": len(cues),
        },
        "cues": cues,
    }
    Path(a.out).expanduser().write_text(json.dumps(out, indent=2))
    hosts = sum(1 for c in cues if c["track"] == "host")
    guests = len(cues) - hosts
    print(f"spice_to_egtext: {len(cues)} cues ({hosts} host / {guests} guest) -> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
