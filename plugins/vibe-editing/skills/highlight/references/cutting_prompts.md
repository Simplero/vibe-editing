# /highlight — cutting prompts

These two LLM prompts encode **how Q&A / hotline footage gets cut** into a tight clip. The
verbatim prompt source is preserved next to this file so the skill is self-contained:

- `segmenter_prompt.ts`        — **STAGE 1 (MINE):** long multi-caller recording → topical candidate segments, filler carved out.
- `clipper_hookmeatpayoff.ts`  — **STAGE 2 (CUT):** one segment → tight HOOK → MEAT → PAYOFF edit.

---

## Stage 1 — SEGMENTER (the miner)

**Input** — word-level transcript, two lines per utterance:
```
[LINE N] [startS-endS] full utterance text
[WORDS N] word1@12.30 word2@12.55 ...
```

**Output** — `{"segments":[{id,title,startLine,startSec,endSec,summary}]}`

**Deterministic post-processing (do this in code, not the LLM):**
1. Clamp each `startSec`/`endSec` to within the line's `[startS-endS]`; if the model's value is outside, fall back to the line bound.
2. Force contiguity: segment N's `startLine` = segment N-1's last line + 1; first segment starts at line 0.
3. Drop any segment whose title begins `Filler –` from the candidate pool (it's pump-up / "who's next" / mic-check / ad-read).

## Stage 2 — CLIPPER (the cut)

Roles are fixed: **Speaker 0 = Host**, **Speaker 1 = Guest/Caller**. Per-utterance
`KEEP` / `REMOVE` / `TRIM` (TRIM may use only words already in that utterance; every index
gets a decision; decisions in index order). The arc:

- **HOOK** — grounded in the **Guest's** opening lines: who they are, their problem/goal *with numbers*, the stakes. **Never open on the host.** Protect the numbers.
- **MEAT** — the diagnostic exchange that builds to the insight. Don't over-trim; keep enough that the payoff lands.
- **PAYOFF** — the **Host's** reframe / framework / concrete instruction. **Cut everything after the last payoff. Nothing trails** (no sign-off, no "talk soon").

Two full worked call examples (a membership-pricing call, a seasonality call) live in the `.ts`.

---

## /highlight adaptations

- **Goal = subscribers.** Selection ranking and titles optimize for `subs_per_1k_views`, not CTR. See `selection_rules.md` + `title_rules.md`.
- **16:9 horizontal mids — NOT 9:16.** A highlights channel posts regular videos, so there is **no vertical reframe / face-track step** (that's `/edit`'s job for shorts).
- **Mids run ~3–10 min** (data sweet spot; average views rise with length). Keep the full diagnostic exchange — don't compress to a 60s short.
- **Transcription:** Groq `whisper-large-v3` (word-level), local `faster-whisper` fallback — the kit's standard. The `[WORDS]` format + Speaker 0/1 roles work the same. Reasoning is done by the running skill (Claude) interactively, or via `ANTHROPIC_API_KEY` for unattended batch.
