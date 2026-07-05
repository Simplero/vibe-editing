---
name: audio-enhance
description: >
  Clean/enhance a clip's VOICE audio — denoise, level (even out dynamics), and loudness —
  the same enhancement the content-pipeline does with Auphonic. Uses Auphonic when the
  account has credits, and automatically falls back to a free offline ffmpeg chain otherwise.
  Trigger keywords: enhance audio, clean audio, denoise, voice cleanup, level the audio,
  audio enhancement, auphonic, make the audio better, fix the audio.
---

# audio-enhance — voice cleanup (Auphonic + free local fallback)

Turns raw/soft/noisy voice into a clean, evenly-leveled, loudness-normalized track. This is the
**same enhancement the content-pipeline uses** — engine: **Auphonic** (`auphonic.com`), algorithms
**denoise + leveler + loudness** (the "Voice Cleaner" idea). When Auphonic has no credits or no key,
it falls back to a free **local ffmpeg chain** (highpass → FFT denoise → compressor/leveler →
loudnorm) so it always produces a result.

## Standalone use
```
python3 ${CLAUDE_PLUGIN_ROOT}/skills/audio-enhance/scripts/enhance.py <input audio-or-video> \
        --out <out.wav> [--loudness -16 | --no-loudness] [--no-denoise] [--no-leveler]
```
- Input may be audio OR video (audio is extracted). Output is a 48k stereo WAV.
- `--loudness -16` targets −16 LUFS; `--no-loudness` leaves final loudness to the render `mix` stage.
- Key: `AUPHONIC_API_KEY` in `${CLAUDE_PLUGIN_ROOT}/config/keys.env` (or env). Without it → local chain.
- Auphonic free tier is ~2 h/month and **resets monthly**; when exhausted the skill logs
  `Auphonic unavailable (... credits ...); using local fallback` and still enhances locally.

## How it's wired into the render workflow
It runs as a render **stage** (`skills/render/stages/enhance.py`) inserted **before `mix`** in the
`single` pipeline: `cut → reframe → grade → captions → enhance → mix → leadfix`. So every clip's
voice is cleaned automatically, then `mix` does the final loudnorm + fades (+ music if any).

Per-clip config (in `manifest.json` → `stages.enhance`; all optional):
```json
"enhance": { "enabled": true, "loudness": null, "denoise": true, "leveler": true }
```
- `enabled: false` → passthrough (no enhancement).
- `loudness: null` → let `mix` handle final loudness (recommended); or set a LUFS number to target here.
- If the enhance script or key is missing, the stage passthrough-copies (never breaks a render).

To add it to another pipeline (e.g. `listicle`, `qa`), insert `"enhance"` right before `"mix"` in
`skills/render/pipelines/<name>.json`.

## Notes
- On a clip that ends with a silent branded end card, prefer `--loudness -16` (loudnorm) over the
  no-loudness path — loudnorm won't raise the silent tail's noise floor the way dynamic normalization can.
- Order matters: enhance the VOICE before mixing music. This skill only touches audio; video is copied.
