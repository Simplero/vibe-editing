# SPEAKER Q&A Short-Form — 24-Clip Visual Synthesis

_Derived from per-clip frame analysis of 24 Team Speaker Q&A shorts (The reference editor edits, 2024-11 → 2026-04). Sampled ~9 frames/clip. This document fills the gaps in `QA_FORMAT_SPEC.md` with quantified, engineer-implementable conclusions._

---

## 1. CUT RHYTHM & SHOT LENGTH

- **Average shot length: ~14s; median ~13s.** (16 clips with known duration.)
- **Range: 8.6s (fast) → 27.7s (slow).** The fast end (`GoSlowToGoFast`, `MyBusinessFallsApart`, `MakeItBetterThanRight` ≈ 8.6s) is brisk conversational ping-pong; the slow end (`WhichPathShouldIPursue` 27.7s, `BoatSubscription` 21s, `ShouldISellMyCompany` 20s) is deliberate three-act block cutting.
- **Typical clip = ~7 distinct shot states** (mean 6.7, median 7) regardless of length, so longer clips hold each angle longer rather than adding more cuts.
- **Cadence is SPEAKER-DRIVEN, not metronomic.** Cuts land on speaker turns (cut to whoever is talking) + caption/clause beats. No rapid-fire montage cutting anywhere. Locked-off stage cameras; energy comes from angle switching + word-by-word captions, NOT zoom pushes.
- **Engineer takeaway:** target one angle change roughly every **10–15s**, holding the active speaker's angle for the duration of their beat. Do not cut faster than ~8s/shot or slower than ~28s/shot.

## 2. SPLIT-SCREEN FREQUENCY & PLACEMENT

- **19 / 24 clips (79%) use the 50/50 split-screen.** 5 clips use none (`IMake600K`, `YouCantHaveBoth`, `IDontKnowWhatIWant`, `HowDoIRaisePrices` [solo monologue], `ShouldICreateANewOffer`).
- **It is NOT a hook device.** Of the 19, **only 1** (`GoSlowToGoFast`) uses split-screen in the hook. **18 / 19** use it MID-clip / back-half / end as a reaction or exchange device. This directly contradicts the spec's "Hook (title card → splitscreen Speaker-top → full-screen)" sequence.
- **Layout: Speaker-TOP / guest-BOTTOM, hard horizontal seam at vertical center.** Orientation held in ~17/19; one clip (`MakeItBetterThanRight`) inverted it (presenter top, Speaker bottom) because roles were swapped.
- **Drop shadow on the Speaker panel: rarely confirmable.** Visible/soft in only ~3 clips (`JazzCourses`, `HowDoIGiveUpSomethingILove`, `MyBusinessIsSeasonal`); most show a clean seam with no pronounced shadow. The spec's "drop shadow on Speaker" is a weak/optional signal, not a reliable one.
- **Engineer takeaway:** split-screen is a **recurring mid-clip A/B-reaction layout** triggered when the audience member is the active or reacting party, NOT a hook opener. Default orientation Speaker-top.

## 3. ANGLE USAGE

- **5 spec angles** (split_screen, speaker_main, guest_main, speaker_wide, guest_wide) but **most clips only use 3–4**. `speaker_main` + `guest_main` + `split_screen` is the dominant trio. Wides (`speaker_wide`, `guest_wide`) appear occasionally (≈6–7 clips each); a clean `guest_wide` is the rarest.
- **DEFAULT ANGLE PER SPEAKER = that speaker's MAIN (medium).** When Speaker talks → speaker_main; when guest talks → guest_main. Split-screen overlays during exchanges/reactions. Wides are punctuation (establishing/payoff), not the backbone.
- **Caption color follows the VOICE, not the on-screen face** (confirmed repeatedly, e.g. `DanceStudio` f5-6, `GoSlowToGoFast` f2, `RealEstate` f0-1): Speaker VO over a guest cutaway stays WHITE; guest VO over an Speaker shot goes YELLOW. This is load-bearing for the caption engine.

## 4. COLORGRADE

- **12 / 24 match spec** (Speaker = brighter + warmer + more saturated; guest = cooler/flatter). **4 / 24 are INVERTED** (`DanceStudio`, `WhichPathShouldIPursue`, `KidsOrProfit`, `YouCantHaveBoth`) — there Speaker is on a cool blue/purple STAGE and the guest sits in warm daylight, so the warm/cool assignment flips. Rest are mild/none/solo.
- **Root cause of inversion: the grade follows native room-vs-stage lighting, not a deliberate per-speaker LUT.** When Speaker is on a blue-lit stage and the guest is in a warm conference room, "Speaker = warm" fails. So a hard-coded per-speaker grade should be a **gentle nudge, not an aggressive teal/orange separation** — several "match" clips were explicitly described as moderate, driven by environment.
- **Concrete ffmpeg-implementable direction (apply per-speaker as a finishing nudge, modest amounts):**
  - **Speaker:** lift brightness + saturation slightly, keep neutral-warm.
    `eq=brightness=0.03:saturation=1.12:contrast=1.05` (optionally `colortemperature=temperature=6300` toward warm).
  - **Guest:** cool + slightly desaturate + flatten.
    `eq=brightness=-0.02:saturation=0.93:contrast=0.98, colortemperature=temperature=7200` (push toward blue ~700–900K cooler than Speaker).
  - **Guard:** detect/skip when the guest is clearly the warmer/brighter subject (stage-vs-room inversion) so you don't double-cool an already-cool Speaker stage shot.

## 5. CAPTIONS — VALIDATION

- **SPEAKER = white: 24 / 24 confirmed.** Universal.
- **GUEST = yellow #FED90F: 19 / 24 confirmed.** **GUEST = italic: 20 / 24 confirmed.**
- **Emphasis weight (Black) lands on key + number + payoff words** — confirmed across nearly all clips. Money abbreviated ($2.7M, $600K, $1.3M, 5X), real `$ % ,` symbols preserved, lowercase except proper nouns / `I` / acronyms (CEO, EBITDA, GPS).
- **Caption exceptions (the 5 that break GUEST=yellow-italic):**
  1. `MyBusinessIsSeasonal` — guest speaking is WHITE upright; **yellow is used for NUMBERS/MONEY/PAYOFF** ($1.3M, 5X, "2 things") regardless of speaker. Number-yellow, not guest-yellow.
  2. `WeNeedMoreEmployees` — Speaker captions WHITE but **italic**; yellow applied **per-word** on key terms (cohorts, real-time), never a full yellow-italic guest line.
  3. `ShouldICreateANewOffer` — color is sectioned by **TIME not speaker**: hook (~first 6s) is yellow-italic for BOTH speakers, then the entire rest is white for BOTH.
  4. `HowDoIRaisePrices` — **solo Speaker monologue, no guest**; yellow-italic used as an emphasis/quote dial within one speaker.
  5. `ShouldIInvestInAI` — guest is a **silent reaction cutaway**, never captioned; yellow is Speaker's number/key-term highlight only.
- **Minor italic drift on Speaker:** `IDontKnowWhatIWant`, `WhatKeepsYouGoing`, `WeNeedMoreEmployees`, one line of `GoSlowToGoFast`/`ShouldISellMyCompany` render Speaker captions with a slight italic slant (spec says Speaker non-italic). Tolerated minor; weight/color are the load-bearing dials.
- **Number = yellow digit (Speaker-canon) confirmed independently** in `HowDoIGiveUp` ("10,000"), `IDontKnowWhatIWant` ("3 years"), `YouJustNeedToFocus` ("$500K"), `ShouldIInvestInAI` ("$8M","18 months"), `MyBusinessIsSeasonal` ($1.3M, 5X). So yellow has **two jobs**: (a) the guest-speaker color, and (b) the number/money highlight on Speaker's white lines.

## 6. TITLE CARD

- **0 / 24 clips have an opening title card.** No SF Pro ALL-CAPS headline, no #1A1A1A rounded box, no yellow-keyword overlay in any sampled frame of any clip.
- This is **consistent with the locked "no title-card hooks for Speaker/SF" rule** — another team owns that step. The spec's title-card requirement does NOT reflect shipped Team Speaker Q&A output.
- **The hook is carried by audible question + captions.** Two hook variants observed: (a) **cold-open on the guest/audience member** stating the problem/number ("$3M this year", "$100M", "$2.7M profit", "my question is"), or (b) **open on Speaker** giving the business framing ("we do about $2.5M", "$8M in revenue").

## 7. STRUCTURE PATTERN

- **Dominant arc (all clips): HOOK → TENSION → PAYOFF**, single issue / single widely-applicable solution. Confirmed in ~23/24 (the lone solo monologue still runs single-issue→single-solution).
- **HOOK (~0–8s):** cold problem/number, no card. Guest-stated OR Speaker-framed.
- **TENSION (~mid):** Speaker prompts ↔ guest answers ↔ Speaker digs. ONE issue. Split-screen + A/B cutaways land here. This is where split-screen lives.
- **PAYOFF (final third):** Speaker delivers the generalizable reframe/solution; often a wide or a quoted principle ("feature not bug", "it's rare air", "now can scale").

## 8. NET DELTAS BETWEEN SPEC AND SHIPPED REALITY

| Spec says | Shipped reality (24 clips) |
|---|---|
| Hook = title card → splitscreen → full-screen | **No title cards (0/24); split-screen is mid-clip not hook** |
| Split-screen throughout / hook | **Mid-clip reaction device (18/19 non-hook), 79% of clips** |
| Drop shadow on Speaker panel | **Rarely visible (~3/19); treat as optional** |
| Speaker bright+sat / guest cool+blue | **True 12/24; INVERTS on stage-vs-room lighting (4/24)** |
| Guest = yellow italic / Speaker = white | **Holds 19–20/24; yellow doubles as number-highlight; Speaker occasionally italic** |
| 5 angles | **3–4 in practice; guest_wide rare; per-speaker MAIN is the default** |

---
_Synthesis generated 2026-06-04 from 24 per-clip analyses._
