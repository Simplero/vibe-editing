# /highlight — selection rules (what makes a postable, sub-converting mid)

The miner scores every non-filler candidate segment 0–100 for **subscriber-conversion
potential** (`subs_per_1k_views`). `highlight_miner.py score` computes the math; Claude supplies
the judgment fields (below) while segmenting, following `cutting_prompts.md`.

## The 7 scored dimensions (weights sum to 100)

| Dimension | Wt | What earns it |
|---|---|---|
| **Payoff** | 30 | A single concrete host reframe/framework/instruction the segment pays off on. **No payoff → score collapses** (this is the #1 filter — a clip with no payoff is not postable). |
| **Portability** | 20 | The lesson lands for a stranger NOT in that exact niche. (The #1 historical lesson: portable beats hyper-niche.) Advice that "goes for everybody" scores high; advice only one narrow business could use scores low. |
| **Hook numbers** | 15 | The guest's problem is concrete and carries real numbers — revenue, targets, close rate, price, churn. Numbers = stakes = stop-scroll. |
| **Title pattern** | 10 | The best of the 3 title options matches a high-`f1k` pattern (see `title_rules.md`): watch-if / You / quoted-Q / Helping rank high; Why / vague rank low. |
| **Duration** | 10 | 3–10 min = full marks (data sweet spot, average views rise with length). 90s–3min ok. <90s or >20min penalized. |
| **Self-contained** | 10 | Opens cold on the problem; no dangling references to earlier callers / "like I said". A first-time viewer understands it. |
| **Topic on-brand** | 5 | The channel's core topics (set yours in `config/patterns.json` `on_brand_topics`) > off-brand tangents. |

`score ≥ 55` = postable (configurable in `patterns.json`).

## Judgment fields Claude provides per segment (in `_segments.json`)

```json
{
  "id": 1, "title_options": ["...", "...", "..."],
  "start_line": 0, "end_line": 14, "startSec": 0, "endSec": 273,
  "is_filler": false,
  "business_type": "lead-gen agency  ->  Lead-Gen Company",   // raw + chunked-up-one-level
  "hook_line": "verbatim guest problem (with numbers)",
  "payoff_line": "verbatim host framework/reframe",
  "payoff_strength": 0.9,        // 0..1 — how concrete/sharp/contrarian is the payoff
  "portability": 0.8,            // 0..1 — usefulness to a non-niche viewer
  "self_contained": 0.9,         // 0..1 — cold-open comprehension
  "primary_topic": "offers",
  "numbers": ["$10k", "20%"],
  "summary": "1-2 sentences"
}
```

## Hard disqualifiers (drop the candidate)
- Title prefixed `Filler –` (pump-up, "who's next", mic check, ad read).
- No identifiable payoff.
- Trails past the payoff (sign-off, "talk soon", banter) — the cut must end on the payoff.
- Requires a previous caller's context to make sense.

## What the miner does NOT optimize for
Raw views / CTR. The pattern shows the highest-CTR styles (Why / curiosity / reaction) are
the worst sub-converters. If a one-off **reach** play is wanted, that's a manual override,
not the default.
