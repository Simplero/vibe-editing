# Calvin's editing principles (learned from feedback)

Read this BEFORE designing any clip's cut. Each principle was extracted from Calvin's own
feedback and confirmed by him. When Calvin gives new feedback, extract the underlying
principle, state your assessment, ask him to confirm, then append it here.

## P0 — Consent / sharing boundaries (HARD GATE, check FIRST)
Before generating ANY content from a source (short, mid, full, carousel, quote, written post),
check the project folder for **`SHARING_CONSIDERATIONS.md`** + **`sharing_exclusions.json`**.
Reject or re-cut any candidate clip whose source window overlaps a hard-exclude range. Use
`lib/_shared/sharing_guard.py <project> <in> <out> …` (exit 1 = blocked). For a NAMED guest with
no consent file, STOP and ask — never assume "no file = anything goes."
- Source: Kirsten (2026-06-26) consented to public use EXCEPT anything mentioning her family
  (parents/siblings, mother especially). 9 excluded source ranges recorded.
- Status: **CONFIRMED — non-negotiable**

## Principles

### P1 — The speech must FLOW and be COHERENT (esp. the opening)
The assembled words must read as natural, complete, coherent speech — not a fragment, not a
mid-thought drop-in, not a disfluent ramble. This is about the whole cut flowing, with the
opening line especially needing to stand on its own as a complete thought.

**METHOD (do this every time, don't eyeball it):**
1. Read the FULL transcript around the moment (wide context, not just the target line).
2. EDIT it on paper first — compose the exact complete, flowing sentence(s) you want, which
   may require splicing out disfluencies/redundancies from the middle ("that's, that's not
   who we are…").
3. CLIP just that part together (build the sub-segment).
4. VERIFY with tools — re-transcribe the clipped audio (Groq) and read it back: does it say a
   coherent, complete sentence? Also check energy/boundaries so no word is clipped.
5. ITERATE — keep tweaking splice points until it genuinely flows and is coherent. Only then
   build the full clip.
- Source: clip 1b opened on a fragment ("that we all deserve…"). Calvin: "it needs to flow…
  look at the full transcript, edit to form a complete sentence, clip it, run it through the
  verification tools to see if it makes sense, keep tweaking until it flows and is coherent."
- Status: **CONFIRMED** (2026-07-03)

### P2 — End on a warm, complete button
Land the clip on a resonant, complete sentence that gives closure — ideally a human,
slightly warm line rather than a hard tactical stop.
- Source: Calvin liked ending on "…and it's kind of a nice world to live in."
- Status: **confirmed pending** (2026-07-03)

### P3 — Let transitions breathe (hold a beat)
Don't jump-cut straight from one thought into the next. Hold a short beat (~0.4–0.5s) —
technically a freeze of the last frame + silence — at:
- a SPEAKER CHANGE (e.g. after the guest finishes, before the host responds), and
- a RHETORICAL PIVOT within one speaker (e.g. before "My point is…", before a reframe/punchline).
The cut should feel like the person paused to land the thought, not rushed into the next line.
- Source: Calvin, clip 1b — "hold it for a split second longer" after Kirsten before he speaks;
  "also hold for a beat before 'my point is'."
- Status: **confirmed pending** (2026-07-03)

### P4 — HD for Calvin, always (multicam default)
Whenever Calvin is the on-screen speaker, use his **HD camera** (Ecamm), never the softer
Speaker View. Use the Zoom **Speaker View only for the guest**. This applies to EVERY clip —
shorts AND mids — not just hero clips. Mechanism: detect who's on screen per moment (the Zoom
Speaker View auto-switches; classify by background — e.g. guest's distinct backdrop), then
composite: Calvin intervals ← HD (aligned by the measured HD↔Zoom offset, re-verified per clip
because it can drift over a long recording), guest intervals ← Speaker View.
- Source: Calvin — "use the HD whenever it's me, then merge in speaker view of her… Same for
  all the Shorts. Always. If HD exists, always use that for the vid of me."
- Status: **CONFIRMED — standing default**

### P5 — Lead with the hook (strongest content first), even in mids
Every clip opens on its heaviest-hitting moment — the line that makes someone think "I need to
watch this." Cut filler/throat-clearing/ramp-up openings ("deeper but like what I'm seeing is
that like if you're…"). If the strongest line is buried in the middle, PULL IT TO THE FRONT
(reorder the source windows), then unfold the rest. **A mid is NOT exempt from needing a hook** —
it still competes for the click; it just has more room after the hook. Practical method: scan the
whole segment for the single most arresting/counterintuitive line → that's tail-1 of the open →
build the rest behind it.
- Source: Calvin on the "nervous system" mid — "the first 5 seconds is just filler… the real
  stuff hits at [the childhood line]… pull the best part up to the front so we start with the
  heavy-hitting stuff first, then get into it. The hook of the mid needs to be strong."
- Status: **CONFIRMED — standing default**

### P6 — Titles/labels must be TRUE to the content
The title must describe what's actually said, not an approximation that sounds catchy. Don't
overstate or mislabel the mechanism.
- Source: "Why Your Nervous System Hides Money" was wrong — it doesn't hide money; Calvin says
  the subconscious "makes sure that money stays away." Retitle to what he actually says.
- Status: **CONFIRMED**

### P7 — Caption rules (BINDING, auto-applied to every render)
Three caption rules are wired into the kit so they run on every clip automatically — no per-clip
config needed. Toggles live in the caption preset (`caption-clips/presets/calvin.json`).
- **P7a — Per-clip placement (most important).** Captions are NOT a fixed Y. The captions stage
  runs `horizontal-to-vertical/scripts/layout_analyze.py` on the reframed 9:16 footage: it
  face-tracks the clip, then drops the caption into the open band **below the chin**, clamped into
  the platform-safe zone (never over the eyes/mouth, never in the bottom UI band). Wired via
  `captions.no_layout=false` (the default). Calvin 2026-07-05: "the captions are right over my
  eyes… look at the footage to determine the best placement."
- **P7b — Asterisk swears.** Profanity is masked in the **burned caption text only** (audio is
  never touched): first + last letter kept, middle asterisked (fucking → f\*\*\*\*\*g, shit →
  s\*\*t). Implemented at the display chokepoint in `generate_spice.py` (`mask_profanity`); toggle
  `mask_profanity` (default ON). Innocent look-alikes (class/pass/assume) never match.
- **P7c — Brand-yellow emphasis pops.** The key word per caption line pops in brand yellow
  **#FFD643** — the director's weighted word when the LLM path runs, else the strongest content
  word (heuristic). One pop per line, tasteful. `generate_spice.py` (`emph_idx`); toggle
  `emphasis_color_enabled` (default ON), colour `emphasis_color`. To FORCE a director-specified
  payoff word (overriding the heuristic + the function-word skip), set the captions-stage config
  `emphasis_force_last: ["<word>"]` — pops the LAST occurrence of that word (e.g. `["you"]` lands
  the closing "the value is YOU" in yellow, Calvin 2026-07-05).
- Status: **CONFIRMED** (implemented 2026-07-05; reference clip "The value is you" v2).

## Meta-principle — how to keep improving
Every time Calvin gives feedback on a clip:
1. Extract the underlying PRINCIPLE (not just the one-off fix).
2. State your assessment of that principle to him.
3. Ask him to confirm (he may refine it).
4. Append the confirmed principle here so all future clips apply it automatically.
