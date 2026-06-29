# /highlight — the closed loop + how it learns

```
raw recording
 → /highlight: transcribe → mine → score+title (highlight_miner.py)
 → cut 16:9 (highlight_cut.py → lib/_shared/precision_cut.py) [+ optional brand/cta/outro.mp4]
 → upload as drafts (manually, or highlight_publish_bridge.py --yes-upload)
 → POST: titles (title_sop.py, subs-optimized) + schedules to YOUR channel (highlight_post.py)
 → POSTED
 → [feedback] Studio re-export → highlight_studio_import.py → numbers widen
 → miner scoring + title patterns sharpen on the next run
```

## Two learning mechanisms

### 1. mid → source linkage — `highlight_source_match.py`
Links a mid back to the longer video it was cut from, by transcript overlap (which longer
video contains a mid's word-shingles). Gives you real **mid ↔ full-source pairs** to learn cut
patterns from, and answers "compare the mid to the full video." Works against a **local library
of your own transcripts** (a directory of `*.json`/`*.txt`, or a simple SQLite table you build)
— no external service. Mids whose source isn't in your library are reported unlinked — the
honest "can't link it" set (expected for live Q&A/hotline whose raw isn't published).

### 2. performance refresh — `highlight_studio_import.py`
The weights in `config/patterns.json` ship as starter defaults. Pull a fresh YouTube Studio
"Table data.csv" monthly and import it to widen + refresh the numbers behind your weights.
Preview by default; `--write-db` persists to a local SQLite file you control.

## The measurement that closes the loop
Tag the titles you publish with the rule version you used. After a Studio refresh, compare the
median `subs_per_1k_views` of titles written with the subs-optimized rules vs older ones to prove
the rules actually moved the needle, then tune `config/patterns.json` (the pattern→f1k weights)
on the widened data. That's the loop: post → measure → re-weight → mine better.

## Cadence (suggested)
- Each new raw recording → `/highlight` → review → cut → upload → POST.
- Monthly → Studio export → `highlight_studio_import.py --write-db` → re-check `patterns.json`
  weights against the fresh numbers.
