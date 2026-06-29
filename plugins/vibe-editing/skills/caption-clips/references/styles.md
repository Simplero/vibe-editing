# Caption styles — full spec

## UGC

Clean, native-style UGC captions. Feels native, not produced.

- **Font:** Poppins SemiBold (drop `Poppins-SemiBold.ttf` in `fonts/`)
- **Size:** 88px at 1080×1920
- **Color:** Pure white
- **Shadow:** Soft drop shadow — black, ~50% alpha, 0px x / 4px y offset, ~8px blur (ASS `\shad` + `\blur`)
- **Stroke:** None. Shadow only.
- **Case:** lowercase (natural UGC feel)
- **Punctuation:** stripped (no periods, commas, question marks, exclamation). Apostrophes kept.
- **Position:** ~72% from top of frame — lower-third, above the bottom UI safe area, below the typical talking head.
- **Words per screen:** 2–3, cap at 18 chars. Prefer breaking on natural speech pauses.
- **Animation:** subtle pop-in — each chunk scales 0.88 → 1.00 over 90ms. No bounce, no overshoot.
- **Active-word highlight:** opacity boost only (inactive words sit at ~70% alpha, the word being spoken pops to 100%). No color change.

## Pro

Creator-lineage / business-operator vibe. Same clean base, but weight shifts on emphasis words — that's the signature move.

- **Font family:** Montserrat (drop all .otf files in `fonts/`). Used variants:
  - **Medium** — base/default weight for most words
  - **Bold** — emphasis words (numbers, emphatic language, key concepts)
  - **Bold Italic** — quoted phrases or callouts ("he said...", book titles, proper nouns being introduced)
  - **Semibold** — soft emphasis, proper nouns that are just mentioned
- **Size:** 82px at 1080×1920 (slightly smaller than UGC to accommodate more chars per line)
- **Color:** Pure white across all weights (highlighting is weight-only, not color)
- **Shadow:** Same as UGC — soft drop shadow, no stroke
- **Case:** Sentence case (keeps the polished feel). Capitalize proper nouns and the first word of each chunk.
- **Punctuation:** stripped. Apostrophes and hyphens kept.
- **Position:** ~72% from top (same as UGC)
- **Words per screen:** 3–4, cap at 22 chars. A longer read is OK because the weight variation gives the eye handles.
- **Animation:** same pop-in (scale 0.92 → 1.00 over 80ms, less aggressive than UGC).
- **Active-word highlight:** opacity boost only, same as UGC.

### Emphasis-word selection rules (Pro only)

When generating the `.ass` for Pro style, walk the transcript and classify each word:

1. **Quote weight (Bold Italic)**
   - Words appearing inside direct quotes in the transcript.
   - Words following "he said," "she said," "they said," "I said" until the next clause break.

2. **Emphasis weight (Bold)**
   - Numbers, including spelled-out ("fifty", "one million") and digits ("50", "1,000,000").
   - Currency mentions ("$500", "ten dollars").
   - Words from the preset's `list_of_emphasis_words` array (never, always, every, secret, key, proof, truth, etc — tweak the list in `presets/pro.json`).
   - Sentence-final punchline words (last 1–2 content words before a long pause > 600ms).

3. **Soft weight (Semibold)**
   - Proper nouns (detected by the spaCy NER pass or by uppercase-start heuristic when spaCy isn't available).

4. **Base weight (Medium)**
   - Everything else.

Only one weight per word — if multiple rules match, priority is Quote > Emphasis > Soft > Base.

Cap the emphasis rate at ~30% of words per clip. If the rules produce more than that, keep the highest-priority hits and demote the rest to Medium — too much weight variation loses the effect.

## Shared rules

- **Safe area.** Keep text between 8% and 92% horizontally. Vertically: never above 60% (face region) or below 85% (IG UI overlay).
- **Word chunking.** Never split a chunk mid-word. Prefer breaking on natural pauses — if two words have a gap > 200ms between them, always break there.
- **Display timing.** A chunk stays on screen from the first word's start time to the last word's end time + a 120ms trailing buffer so it doesn't flash off mid-syllable.
- **Minimum chunk duration.** If a chunk would be on screen for < 400ms, merge it with the neighbor. Flashing captions are unreadable.
- **No overlap.** Back-to-back chunks must not overlap in time. If they would, shorten the earlier chunk.

## Adding your own style

1. Copy `presets/ugc.json` to `presets/<yourname>.json`, tweak values.
2. Add `--preset presets/<yourname>.json --style <yourname>` to the caption-burner call.
3. Drop any new font files in `fonts/`.
