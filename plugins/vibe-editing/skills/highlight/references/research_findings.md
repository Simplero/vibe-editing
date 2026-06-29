# Highlights-channel clipping & titling — the method

The empirical basis for `/highlight` and the title rules. These are general findings from
running a business-Q&A highlights channel (a second channel that posts horizontal "mid"
clips); the *numbers* below are illustrative of the pattern, not any specific channel's stats.
Re-derive them on your own data with `highlight_studio_import.py`.

## 1. What a "mid" is
- A **highlights channel** posts **long, 16:9, ~1–10 min** clips (NOT 9:16 shorts): live or
  phone Q&A (a host + a business owner), hotline calls, and generic podcast/YouTube clips.
- The companion **main channel** posts the polished monologues; the highlights channel posts
  the raw-but-edited gold from long recordings. The two have different jobs.

## 2. KPI = subscriber conversion, not views
- The metric that matters for a highlights channel is **`subs_per_1k_views = subscribers_gained
  ÷ views × 1000`** — how efficiently a clip turns a viewer into a subscriber.
- Measure it from your own YouTube Studio export. Treat it as a **snapshot** (re-pull
  monthly). Studio's auto `primary_topic` column is often miscalibrated — don't trust it; set
  the topic yourself while segmenting.

## 3. THE finding — CTR and subscriber-conversion are DECOUPLED
The highest-CTR title styles ("Why…", vague curiosity, reaction/personality) tend to be the
**worst** sub-converters; "You/…" declaratives, quoted questions, and contrarian takes are
the **best**. Illustrative:
- A plainly-worded quoted question — low CTR but **high follows/1k**
- A reaction/personality title — high CTR but **near-zero follows/1k**
- A blunt "You need to…" command — high on **both** (the ideal)
→ **Optimize titles + selection for subscribers, not CTR.** (Full ranking in `title_rules.md`.)

## 4. Duration
Mids run 1–10 min; **sweet spot 3–10 min**; average views tend to rise with length. Keep the
full diagnostic exchange — don't compress a mid down to a 60s short.

## 5. How Q&A/hotline mids are cut
**Open on the guest/caller's problem** (who they are + real numbers + stakes — *never* open on
the host) → host diagnoses/reframes → **end the instant the payoff lands; nothing trails** (no
sign-off/banter). Pure filler (pump-up, mic-check, "who's next", ad-reads) is carved out. Two
LLM stages: SEGMENTER (topic/filler boundaries) + CLIPPER (HOOK→MEAT→PAYOFF, per-utterance
KEEP/REMOVE/TRIM). The prompts are in `segmenter_prompt.ts` + `clipper_hookmeatpayoff.ts`.

## 6. Pipeline shape
Transcript + LLM only — **no vision** in the miner. Transcribe word-level + diarized, segment,
score+title, cut 16:9. Reasoning runs interactively (Claude in the skill) or unattended via
`ANTHROPIC_API_KEY`.

## 7. The closed loop (how it learns)
raw recording → **/highlight** (transcribe → mine → score+title → cut 16:9 → render) → upload
as drafts → **POST** (titles + schedules to your channel) → posted → re-pull Studio data →
re-weight `config/patterns.json` → sharpen selection + titles on the next run.

## 8. Optional learning aids
- `highlight_source_match.py` — link a mid back to the longer source it was cut from (transcript
  overlap), so you can compare the mid to the full video. Works on a **local library of your own
  transcripts** — no external service.
- `highlight_studio_import.py` — import your own Studio CSV to widen + refresh the numbers the
  weights are tuned against.
