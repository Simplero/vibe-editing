#!/usr/bin/env python3
"""
highlight_studio_import.py — import YOUR OWN YouTube Studio export to tune the weights.

The selection + title weights in config/patterns.json ship as starter defaults. To make them
yours, export your channel's analytics from YouTube Studio as a CSV ("Table data.csv": Content /
Views / Impressions CTR / Subscribers / Estimated revenue / Average view duration) and import it
here. This lets you measure your real subs_per_1k_views (subscribers_gained ÷ views × 1000) per
video and re-rank the title patterns against YOUR data.

Everything is LOCAL — it reads your CSV and writes to a local SQLite file you control. No
external service, no shared database.

🛑 Writing requires explicit --write-db. Default = dry-run preview.

Usage:
  highlight_studio_import.py --csv ~/Downloads/"Table data.csv"                  # preview
  highlight_studio_import.py --csv ~/Downloads/"Table data.csv" --out report.json
  highlight_studio_import.py --csv ~/Downloads/"Table data.csv" --write-db       # persist to local SQLite
  # default db path: <repo>/brand/analytics/yt_analytics.db  (override with --db)
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
REPO_ROOT = _os.path.dirname(_os.path.dirname(VIBE_ROOT))   # parent of plugins/
DEFAULT_DB = _os.path.join(REPO_ROOT, "brand", "analytics", "yt_analytics.db")
# ── end bootstrap ──
import argparse, csv, json, re, sqlite3
from datetime import date


def find_col(headers, *needles):
    for h in headers:
        hl = h.lower()
        if all(n in hl for n in needles):
            return h
    return None


def to_sec(s):
    s = (s or "").strip()
    if re.match(r"^\d+:\d{2}(:\d{2})?$", s):
        parts = [int(x) for x in s.split(":")]
        return parts[0] * 60 + parts[1] if len(parts) == 2 else parts[0] * 3600 + parts[1] * 60 + parts[2]
    try:
        return int(float(s))
    except ValueError:
        return None


def num(s):
    try:
        return float(re.sub(r"[^0-9.\-]", "", s or "")) or 0
    except ValueError:
        return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--db", default=DEFAULT_DB, help="local SQLite file to write (default: brand/analytics/yt_analytics.db)")
    ap.add_argument("--out", default="", help="also write a JSON report of parsed rows + subs_per_1k_views")
    ap.add_argument("--write-db", action="store_true")
    a = ap.parse_args()
    if not _os.path.exists(a.csv):
        _sys.exit(f"no such csv: {a.csv}")

    rows = list(csv.DictReader(open(a.csv, encoding="utf-8-sig")))
    if not rows:
        _sys.exit("empty csv")
    H = rows[0].keys()
    col = {
        "id": find_col(H, "content") or find_col(H, "video"),
        "views": find_col(H, "views"),
        "ctr": find_col(H, "click-through") or find_col(H, "ctr"),
        "subs": find_col(H, "subscriber"),
        "rev": find_col(H, "revenue"),
        "avd": find_col(H, "average", "view", "duration"),
        "imp": find_col(H, "impressions"),
    }
    print(f"[import] {len(rows)} rows; column map:")
    for k, v in col.items():
        print(f"   {k:6} <- {v!r}")
    if not col["id"]:
        _sys.exit("could not find a Content/Video id column")

    staged = []
    for r in rows:
        vid = (r.get(col["id"]) or "").strip()
        if not vid or vid.lower() in ("total", ""):
            continue
        if not re.match(r"^[A-Za-z0-9_-]{11}$", vid):   # skip channel-total / non-id rows
            continue
        views = int(num(r.get(col["views"]))) if col["views"] else None
        subs = int(num(r.get(col["subs"]))) if col["subs"] else None
        f1k = round(subs / views * 1000, 2) if (subs and views) else None
        staged.append({
            "video_id": vid, "views": views, "subs_gained": subs,
            "revenue": num(r.get(col["rev"])) if col["rev"] else None,
            "ctr": num(r.get(col["ctr"])) if col["ctr"] else None,
            "avg_view_sec": to_sec(r.get(col["avd"])) if col["avd"] else None,
            "impressions": int(num(r.get(col["imp"]))) if col["imp"] else None,
            "subs_per_1k_views": f1k,
        })
    print(f"[import] {len(staged)} valid video rows parsed")
    for s in staged[:5]:
        print(f"   {s['video_id']}  views={s['views']} subs={s['subs_gained']} f1k={s['subs_per_1k_views']}")

    if a.out:
        json.dump({"rows": staged}, open(a.out, "w"), indent=2)
        print(f"[import] report -> {a.out}")

    if not a.write_db:
        print("\n[DRY-RUN] nothing written. Re-run with --write-db to upsert into your local SQLite.")
        return

    _os.makedirs(_os.path.dirname(a.db), exist_ok=True)
    src = f"Table data.csv (import {date.today().isoformat()})"
    con = sqlite3.connect(a.db); cur = con.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS yt_analytics (
        video_id TEXT PRIMARY KEY, views INTEGER, subs_gained INTEGER, revenue REAL,
        ctr REAL, avg_view_sec INTEGER, impressions INTEGER, subs_per_1k_views REAL,
        src TEXT, imported INTEGER)""")
    n = 0
    for s in staged:
        cur.execute("""INSERT INTO yt_analytics
            (video_id,views,subs_gained,revenue,ctr,avg_view_sec,impressions,subs_per_1k_views,src,imported)
            VALUES (?,?,?,?,?,?,?,?,?,strftime('%s','now'))
            ON CONFLICT(video_id) DO UPDATE SET
              views=excluded.views, subs_gained=excluded.subs_gained, revenue=excluded.revenue,
              ctr=excluded.ctr, avg_view_sec=excluded.avg_view_sec, impressions=excluded.impressions,
              subs_per_1k_views=excluded.subs_per_1k_views, src=excluded.src, imported=excluded.imported""",
            (s["video_id"], s["views"], s["subs_gained"], s["revenue"], s["ctr"],
             s["avg_view_sec"], s["impressions"], s["subs_per_1k_views"], src))
        n += 1
    con.commit(); con.close()
    print(f"[import] ✅ upserted {n} rows into {a.db} (src={src!r})")
    print("[import] Now re-rank config/patterns.json title_patterns against these subs_per_1k_views numbers.")


if __name__ == "__main__":
    main()
