# Q&A V1 Delivery Checklist — THE GATE (locked 2026-06-04)

**RULE:** No Q&A clip goes to the user for review until EVERY box below is ✅. If any is ❌, fix it first.
Run this self-audit (extract frames + inspect) at the end of `qa_assemble`, before staging the file.
This exists because a V1 shipped with all of these unmet — that's a V0.5, not a V1. (User, 2026-06-04.)

## A. FRAMING / REFRAME
- [ ] **Speaker is TRACKED** — the crop follows him as he moves/points/walks; he never drifts off-center or to the edge. (Static crop = fail.)
- [ ] **Guest is TRACKED** — centered medium, follows movement.
- [ ] Both match the **Speaker-Main / Guest-Main medium standard**: head with proper headroom, eyeline ~upper third, waist-up framing.
- [ ] **No distracting foreground audience heads** dominating either shot.
- [ ] Subject horizontally centered through the whole shot.

## B. CUT TIMING / SWITCHING
- [ ] **Cuts land on speech beats** — sentence ends / natural pauses, NOT a fixed timer.
- [ ] **Reaction cutaways are motivated** by a real pause or reaction beat, not an interval.
- [ ] **The speaker is HELD on payoff / punchline lines** — never cut away during the key line.
- [ ] Shot rhythm reads speaker-driven (~10–15s feel), not mechanical.

## C. CAPTIONS
- [ ] **Emphasis authored by the caption-director** (data-backed), not a hand-typed word list.
- [ ] Color follows the **voice** (guest yellow #FED90F / Speaker white); numbers ride the voice.
- [ ] Position/size per spice; sentence-boundary breaks; no early reveal / no lag; zero dead gaps.

## D. GRADE
- [ ] Per-speaker grade in the **correct direction**; **inversion guard** applied when Speaker is on a cool stage & guest in a warm room.
- [ ] No clipping; skin tones natural.

## E. DYNAMICS / POLISH
- [ ] **Not fully static** — subtle punch-ins / slow push on holds; motion where it helps.
- [ ] Clean transitions (no glitch/black frames at cuts or at start/end).
- [ ] Audio clean, **lip-synced**, loudnorm to target (~-14 LUFS), no bleed/echo.

## F. CONTENT GUARDS
- [ ] Profanity flagged to user (mute vs keep) before ship.
- [ ] No "DO NOT USE" guests in the clip.
- [ ] Hook starts at the meat (no "hi my name is"); ends on the climax (no trail-off).

---
**Self-audit method:** `qa_assemble` extracts a frame per shot + at each cut boundary + start/end, runs the
A–F checks, and prints a PASS/FAIL report. Stage the file only on all-PASS. (Build this into the assembler.)
