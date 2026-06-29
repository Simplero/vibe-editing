# Q&A SHORT-FORM SOP — LOCKED at V34 (2026-06-05)

THE STANDARD. Distilled from 34 review rounds on `SPEAKER_SF_WORKSHOP_ExampleQA_Operator_20260416`
(Ricky "never stop a flow"). Reproduce a finished Q&A short from raw 3-cam + iso mics by following
this exactly. The render driver is `/tmp/render_v27.sh` (template) → `qa_assemble.py` base + the
`recut.py` re-time/caption pipeline. **Read this FIRST on any new Q&A.**

## 0. Pipeline shape
raw 3 cams (speaker / guest-main / guest-WIDE room cam) + iso mic WAVs → audio-xcorr sync → moment-mine →
cut. Render = TWO stages: (1) `qa_assemble.py` builds a 1080 BASE (reframes, split tiles, side-cam, shots);
(2) `recut.py` writes a source→cut KEEP map + `cut_filter.txt`, then ONE ffmpeg pass cuts the base +
burns captions + lays clean audio. Iterate in FAST mode (`--res 1080 --no-grade`, no vignette); do the
4K finish ONLY once the cut + captions are locked.

## 1. Reframe (full-screen shots)
Speaker-LOCKED detect (`qa_detect_speaker.py` ROI, never largest-face=audience) → `reframe_h2v.py`
(per-frame X-track, Y-locked). Speaker zoom **1.9**, nose-y-1080 **430** (head-to-thigh per SOP). Guest zoom **1.25**.

## 2. Split screen (Speaker TOP / guest BOTTOM)
- **Dedicated 1080x960 tiles**, reframed straight from the 4K cams — NOT crops of the pre-zoomed verticals
  (that grabbed torsos / face-filled). Speaker tile: zoom **2.3**, smooth **21** (heavy smooth lags his pacing),
  nose-x **~460–540** (drop toward 460 if he reads right of center), nose-y-1080 580. Guest tile: zoom **1.35**
  (head+shoulders, audience cropped). Wire via `qa_assemble --split-tile --guest-split-tile`.
- **Seam = ONE-SIDED soft drop shadow** (`assets/seam_shadow.png`, half-gaussian, peak **0.60**, sigma 34),
  overlaid with its top ON the 50% seam so it falls DOWNWARD onto the GUEST only — Speaker's panel keeps a clean
  edge. NOT symmetric, NOT drawbox bars. Grounded in the reference editor's real clips (your review tool 2026 TEAM SPEAKER exports).
- Captions during a split sit at the **seam, ~50%** (`--split-y 0.50`).

## 3. Side cam = the guest WIDE / 3rd cam (Q&As NEED this)
The 3rd cam is a full-room establishing wide; **crop it TIGHT on the standing guest** to fake the reference editor's
dedicated guest-wide (the style guide OMITS this cam — use the reference editor's finished clips as the ref instead).
Target: guest **head in the TOP THIRD**, centered/center-left, seated audience as foreground along the bottom.
Heavy crop (~320x569 from 4K) + `scale=…:flags=lanczos,unsharp=5:5:0.8` to fight the softness. Captions on
the side cam go at **ELBOW height (~48%)** (`--gw-y 0.48`), NOT the bottom. Switch in/out ON caption boundaries.

## 4. CAPTION CONTINUITY — the hard-won rule (`qa_caption_layout.py`)
Captions must be CONTINUOUS across every camera switch — no gaps, no bleed, no early pop. Implementation:
assign each cue to a shot by its **MIDPOINT** (→ that angle's height), then fill every shot EDGE-TO-EDGE:
the LAST cue holds out to the cut (`shot.end`); the FIRST cue starts **one frame AFTER the cut** (`shot.start
+ 0.04`) so the incoming speaker's caption never lands on the outgoing shot's final frame. Heights: speaker 0.47,
guest 0.674, split 0.50, guest_wide 0.48. (libass is end-exclusive → outgoing/incoming meet cleanly.)
**Align camera cuts to caption/word boundaries** so a caption owns exactly one angle.

## 5. Caption text & style
Unified **spice**. Color = VOICE (white Speaker / yellow `#FECB00` guest). caption-director per-word weight/size/
italic. **Size bump (peak) only on single-word cues** — e.g. enlarged "new[s]". Stylistic text via the transcript:
`guy-.` renders "guy-" AND keeps the chunk break; `new[s]` keeps brackets (disp() preserves inner punctuation).
When the chunker drifts off a phrase Brand wants, **pin it with `ass_move_i.py`-style .ass surgery**
(it hard-packs "I don't like two" onto one line and force-sizes new[s] regardless of chunking).

## 6. Editorial cuts (`recut.py` REMOVE list = source-time ranges)
**Silence-snap** every cut — land on acoustic energy dips, NOT whisper word ends (off 150–250ms → leaves
snippets). **Fused phonemes can't be split** ("so you" is one blob → keep "so you" whole). Trim dead air,
fillers, hedges (cut the whole hedge incl. orphans like "which"), and trailing reaction sounds. Start the clip
on the hook (cut "god,"). Map Brand's your review tool timecodes → source via the KEEP-segment inverse.

## 7. Audio — keep it CLEAN
Active-speaker mic mix (LAV=Speaker, MIC=guest, sidechain duck) → ElevenLabs `isolate_audio`. The CUT: trim +
concat + **8ms declick afades** + single **AAC 320k**. **NO loudnorm, NO limiter, NO double-encode** — that
stack = the "terrible audio". (TP-vs-`-6` gate is a final-master concern; never chase it with processing that
wrecks the sound.)

## 8. Master finish (LAST, once locked)
Re-render at 4K → **Topaz upscale via Higgsfield MCP** (the soft tight stage-cam crops) → color correction
(company punch) → **vignette + gaussian blur** (`apply_vignette.py`: gblur sigma 15 + eq brightness -0.12
edge plate) → burn captions at 4K → clean audio.

## 9. Naming (Brand SOP, mandatory)
`BRAND_CONTENTTYPE_SOURCE_Title_Editor_YYYYMMDD_V#` → **SPEAKER_SF_WORKSHOP_<Title>_Operator_<shootdate>_V#**.
SF=short-form, SOURCE=**WORKSHOP** for the live audience Q&A, date = FOOTAGE-shot date (not render date),
V# increments forever (never overwrite).

## 10. Review loop
Pull Brand review notes from your review tool via the V4 API: `revise-from-comments/scripts/fetch_comments.py`. A clip is a
**version_stack** — pass the version's file_id; comment `timestamp` is a FRAME INDEX (÷ fps for seconds).
Address each note by timecode; re-fetch each round. (Brand just comments on the version; no .txt needed.)
