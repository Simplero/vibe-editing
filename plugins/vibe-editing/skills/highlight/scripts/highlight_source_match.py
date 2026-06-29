#!/usr/bin/env python3
"""
highlight_source_match.py — link a mid back to the LONG-FORM source it was cut from.

Given a mid's transcript, take distinctive word-shingles from it and find the longer source
transcript that contains them. This is what lets you compare a mid to its full source and learn
"why this 4-min mid was cut from that 90-min recording."

LOCAL ONLY — it searches a directory of YOUR OWN transcripts (no external service, no shared
database). Each candidate is a transcript file: either plain text (.txt/.vtt/.srt) or JSON
with a top-level "text" field or a "words" list. Point --library at the folder of long-form
transcripts; point --mid at the mid's transcript file (same formats).

Usage:
  highlight_source_match.py --mid 10_WORK/mid.json --library 10_WORK/transcripts/
  highlight_source_match.py --mid mid.txt --library sources/ --out match.json
"""
import argparse, json, os, re, glob

SH = 8                      # shingle length (words)
POS = (0.20, 0.40, 0.60, 0.80)


def toks(t):
    return re.sub(r"[^a-z0-9 ]", " ", (t or "").lower().replace("&gt;", " ")).split()


def read_transcript(path):
    """Return plain text from .txt/.vtt/.srt or JSON ({"text":...} or {"words":[{"word":...}]})."""
    raw = open(path, encoding="utf-8", errors="replace").read()
    if path.lower().endswith(".json"):
        try:
            j = json.loads(raw)
        except Exception:
            return raw
        if isinstance(j, dict):
            if j.get("text"):
                return j["text"]
            words = j.get("words") or (j.get("segments") and [w for s in j["segments"] for w in s.get("words", [])])
            if words:
                return " ".join(w.get("word", w.get("text", "")) for w in words)
        return raw
    # vtt/srt: drop cue numbers + timestamps
    lines = []
    for ln in raw.splitlines():
        ln = ln.strip()
        if not ln or "-->" in ln or ln.isdigit() or ln.startswith(("WEBVTT", "Kind:", "Language:")):
            continue
        lines.append(ln)
    return " ".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mid", required=True, help="the mid's transcript (.json/.txt/.vtt/.srt)")
    ap.add_argument("--library", required=True, help="folder of long-form source transcripts")
    ap.add_argument("--min-hits", type=int, default=2, help="shingles that must match to call it the source")
    ap.add_argument("--out", default="")
    a = ap.parse_args()

    cand_files = []
    for ext in ("json", "txt", "vtt", "srt"):
        cand_files += glob.glob(os.path.join(a.library, f"**/*.{ext}"), recursive=True)
    cand_files = [f for f in cand_files if os.path.abspath(f) != os.path.abspath(a.mid)]
    if not cand_files:
        _sys = __import__("sys"); _sys.exit(f"no transcript files found under {a.library}")

    mtext = read_transcript(a.mid)
    wt = toks(mtext)
    if len(wt) < SH * 2:
        print(f"[match] mid transcript too short ({len(wt)} words) to fingerprint."); return
    shingles = [" ".join(wt[int(p * len(wt)):int(p * len(wt)) + SH]) for p in POS]
    shingles = [s for s in shingles if len(s.split()) == SH]

    cand_norm = [(f, " ".join(toks(read_transcript(f)))) for f in cand_files]
    print(f"[match] mid {os.path.basename(a.mid)} vs {len(cand_norm)} candidate source transcript(s)")

    best = None
    for f, ntext in cand_norm:
        if len(ntext.split()) <= len(wt):     # a source is LONGER than the mid
            continue
        hits = sum(1 for s in shingles if s and s in ntext)
        if hits and (best is None or hits > best["hits"]):
            best = {"source_file": f, "hits": hits, "of": len(shingles)}

    if best and best["hits"] >= a.min_hits:
        result = {"mid": a.mid, "source": best["source_file"],
                  "hits": best["hits"], "of": best["of"],
                  "confidence": round(best["hits"] / len(shingles), 2)}
        print(f"  ✅ source: {os.path.basename(best['source_file'])} "
              f"[{best['hits']}/{best['of']} shingles, conf {result['confidence']}]")
    else:
        result = {"mid": a.mid, "source": None,
                  "reason": "no source in library (raw likely not in your transcript folder)",
                  "best_partial": best}
        print(f"  —  no source found (best {best['hits'] if best else 0} shingles)")

    if a.out:
        json.dump(result, open(a.out, "w"), indent=2)
        print(f"[match] -> {a.out}")


if __name__ == "__main__":
    main()
