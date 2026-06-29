#!/usr/bin/env python3
"""
/highlight miner — turn a raw Q&A / hotline / podcast recording into RANKED, postable
mid candidates for a highlights channel, optimized for subscriber conversion
(subs_per_1k_views).

Two deterministic stages (the LLM judgment in between is done by the running skill —
Claude — per references/cutting_prompts.md + selection_rules.md + title_rules.md, or by
an API call in headless mode):

  1) format   raw transcript            -> numbered utterances ([LINE N] ...) + outline
       (Claude then segments this into _segments.json using the SEGMENTER prompt)
  2) score    _segments.json            -> candidates.json + review.md  (ranked, filler dropped)

Stdlib only. Mechanics + math live here; editorial judgment lives in the SOPs.
Runs standalone — no external database, no network call.
"""
import argparse, json, os, re, html, sys

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.normpath(os.path.join(HERE, "..", "config", "patterns.json"))


# ----------------------------------------------------------------------------- format
def _clean(text):
    text = html.unescape(text or "")
    text = text.replace("&gt;&gt;", ">>").replace(">>", " >> ")
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def utterances_from_text(text):
    """Split a plain transcript into speaker utterances. Transcripts mark speaker
    turns with '>>' ; if absent we fall back to sentence grouping so LINE numbers still
    map to coherent chunks."""
    text = _clean(text)
    parts = [p.strip() for p in text.split(">>")]
    parts = [p for p in parts if p]
    if len(parts) <= 1:
        # no speaker markers -> group into ~1-2 sentence utterances
        sents = re.split(r"(?<=[.?!])\s+", text)
        parts, buf = [], ""
        for s in sents:
            buf = (buf + " " + s).strip()
            if len(buf) > 160 or s.endswith(("?", "!")):
                parts.append(buf); buf = ""
        if buf:
            parts.append(buf)
    return parts


def cmd_format(args):
    raw = open(args.infile, encoding="utf-8", errors="replace").read()
    utts = utterances_from_text(raw)
    lines, outline = [], []
    for i, u in enumerate(utts):
        lines.append(f"[LINE {i}] {u}")
        outline.append(f"[LINE {i}] {u[:72]}{'…' if len(u) > 72 else ''}")
    out = args.out or os.path.splitext(args.infile)[0] + ".miner_input.txt"
    outl = os.path.splitext(out)[0].replace(".miner_input", "") + ".outline.txt"
    open(out, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    open(outl, "w", encoding="utf-8").write("\n".join(outline) + "\n")
    print(f"[format] {len(utts)} utterances -> {out}")
    print(f"[format] compact outline (read this to find segment boundaries) -> {outl}")
    print(f"[format] NOTE: no word-level timestamps in this source — startSec/endSec will be approximate. "
          f"For production, transcribe word-level first (caption-clips/scripts/transcribe_lv3.py).")


# ------------------------------------------------------------------------------ score
def load_cfg():
    return json.load(open(CONFIG, encoding="utf-8"))


def match_pattern(title, cfg):
    for p in cfg["title_patterns"]:
        try:
            if re.search(p["regex"], title or ""):
                return p
        except re.error:
            continue
    return cfg["title_patterns"][-1]


def best_title(options, cfg):
    """Pick the title option whose pattern scores highest (ties -> Claude's order)."""
    best, best_pts, best_pat = None, -1, None
    for t in (options or []):
        pat = match_pattern(t, cfg)
        if pat["points"] > best_pts:
            best, best_pts, best_pat = t, pat["points"], pat
    return best, best_pat


def duration_score(dur, d):
    if dur is None:
        return 0.7
    if d["ideal_min"] <= dur <= d["ideal_max"]:
        return 1.0
    if d["ok_min"] <= dur < d["ideal_min"]:
        return 0.5 + 0.5 * (dur - d["ok_min"]) / (d["ideal_min"] - d["ok_min"])
    if d["ideal_max"] < dur <= d["hard_max"]:
        return 1.0 - 0.6 * (dur - d["ideal_max"]) / (d["hard_max"] - d["ideal_max"])
    return 0.3


def clamp(x, lo=0.0, hi=1.0, default=0.5):
    try:
        return max(lo, min(hi, float(x)))
    except (TypeError, ValueError):
        return default


def score_segment(seg, cfg):
    w = cfg["weights"]
    title, pat = best_title(seg.get("title_options") or [seg.get("title", "")], cfg)
    dur = seg.get("endSec")
    dur = (dur - seg.get("startSec", 0)) if isinstance(dur, (int, float)) else seg.get("duration_s")

    hook = (seg.get("hook_line") or "")
    has_num = bool(seg.get("numbers")) or bool(re.search(r"[\$£€]|\b\d", hook))
    topic = (seg.get("primary_topic") or "").lower()

    comp = {
        "title_pattern": (pat["points"] / 10.0),
        "payoff": clamp(seg.get("payoff_strength"), default=0.0) if seg.get("payoff_line") else 0.0,
        "hook_numbers": 1.0 if has_num else 0.3,
        "portability": clamp(seg.get("portability")),
        "duration": duration_score(dur, cfg["duration_s"]),
        "self_contained": clamp(seg.get("self_contained")),
        "topic": 1.0 if topic in cfg["on_brand_topics"] else 0.4,
    }
    breakdown = {k: round(comp[k] * w[k], 1) for k in w}
    score = round(sum(breakdown.values()))
    return {
        "score": score, "recommended_title": title, "title_pattern": pat["name"],
        "title_f1k_proxy": pat["f1k"], "duration_s": dur, "breakdown": breakdown,
    }


def cmd_score(args):
    cfg = load_cfg()
    data = json.load(open(args.segments, encoding="utf-8"))
    segs = data.get("segments", data) if isinstance(data, dict) else data
    os.makedirs(args.out_dir, exist_ok=True)

    cands, dropped = [], []
    for seg in segs:
        if seg.get("is_filler"):
            dropped.append(seg.get("title", f"line {seg.get('start_line')}")); continue
        sc = score_segment(seg, cfg)
        cands.append({**seg, **sc})
    cands.sort(key=lambda c: c["score"], reverse=True)

    floor = cfg.get("min_score_to_post", 55)
    cj = os.path.join(args.out_dir, "candidates.json")
    json.dump({"kpi": cfg["kpi"], "min_score_to_post": floor,
               "dropped_filler": dropped, "candidates": cands},
              open(cj, "w", encoding="utf-8"), indent=2, ensure_ascii=False)

    # human-readable review
    L = []
    L.append(f"# /highlight — mined candidates  (KPI: {cfg['kpi']}, post if score ≥ {floor})\n")
    L.append(f"{len(cands)} candidate(s) · {len(dropped)} filler segment(s) dropped"
             + (f": {', '.join(dropped)}" if dropped else "") + "\n")
    for i, c in enumerate(cands, 1):
        verdict = "✅ POST" if c["score"] >= floor else "⚠️ below floor"
        dur = c.get("duration_s")
        dur_s = f"{int(dur//60)}m{int(dur%60):02d}s" if isinstance(dur, (int, float)) else "?"
        L.append(f"## {i}. [{c['score']}/100] {verdict} — {c['recommended_title']}")
        L.append(f"- pattern: `{c['title_pattern']}` · duration: {dur_s} · topic: {c.get('primary_topic','?')} · business: {c.get('business_type','—')}")
        alts = [t for t in (c.get('title_options') or []) if t != c['recommended_title']]
        if alts:
            L.append(f"- alt titles: " + " · ".join(f'"{t}"' for t in alts))
        L.append(f"- HOOK: {c.get('hook_line','—')}")
        L.append(f"- PAYOFF: {c.get('payoff_line','—')}")
        b = c["breakdown"]
        L.append("- score: " + " ".join(f"{k} {v}" for k, v in b.items()))
        L.append("")
    rv = os.path.join(args.out_dir, "review.md")
    open(rv, "w", encoding="utf-8").write("\n".join(L))
    print(f"[score] {len(cands)} candidates ranked -> {rv}")
    print(f"[score] {cj}")
    postable = sum(1 for c in cands if c["score"] >= floor)
    print(f"[score] {postable}/{len(cands)} at/above post floor ({floor})")


def main():
    ap = argparse.ArgumentParser(description="/highlight miner")
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("format", help="raw transcript -> numbered utterances + outline")
    f.add_argument("infile"); f.add_argument("--out")
    f.set_defaults(func=cmd_format)
    s = sub.add_parser("score", help="Claude's _segments.json -> ranked candidates + review")
    s.add_argument("--segments", required=True); s.add_argument("--out-dir", required=True)
    s.set_defaults(func=cmd_score)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
