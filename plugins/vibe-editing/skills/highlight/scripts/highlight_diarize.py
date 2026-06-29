#!/usr/bin/env python3
"""
highlight_diarize.py — per-word host/guest → fine camera-switch EDL (two-cam Q&A).

Reuses the shared resolve_speakers (mic energy + conversational turn-taking, calibrated
per-clip). Treats the A-cam audio = the host's mic, B-cam audio = the guest's mic (both
PRE-ALIGNED to clip time, so clip-time == mic-time). If the two cam mics demonstrably separate
the speakers, the calibrated mic is ground truth → accurate per-word switching; if not, it
falls back to the content PRIOR + turn-taking. Output: a fine host/guest EDL (A-cam-absolute
time) for highlight_multicam.py.

Inputs:
  --words      whisper json (word-level, clip-relative starts/ends)
  --host-mic   A-cam audio (clip-aligned wav)
  --guest-mic  B-cam audio (clip-aligned wav, already shifted by the sync offset)
  --prior      JSON [{start,end,shot}] CLIP-TIME content labels (rough; the calibration anchor)
  --seg-start  A-cam absolute start of the segment (clip 0) — to emit ABS-time EDL
  --out        output EDL json
"""
# ── vibe-editing portable path bootstrap ──
import os as _os, sys as _sys
def _vibe_root():
    r = _os.environ.get("VIBE_PIPELINE_ROOT") or _os.environ.get("CLAUDE_PLUGIN_ROOT")
    if r and _os.path.isdir(_os.path.join(r, ".claude-plugin")):
        return r
    d = _os.path.dirname(_os.path.abspath(__file__))
    while d != _os.path.dirname(d):
        if _os.path.isdir(_os.path.join(d, ".claude-plugin")):
            return d
        d = _os.path.dirname(d)
    return _os.path.dirname(_os.path.abspath(__file__))
VIBE_ROOT = _vibe_root()
_sys.path.insert(0, _os.path.join(VIBE_ROOT, "skills", "edit", "scripts"))
# ── end bootstrap ──
import argparse, json
from speaker_diarize import resolve_speakers

ap = argparse.ArgumentParser()
ap.add_argument("--words", required=True)
ap.add_argument("--host-mic", required=True)
ap.add_argument("--guest-mic", required=True)
ap.add_argument("--prior", required=True)
ap.add_argument("--seg-start", type=float, required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--min-block", type=float, default=1.6)
ap.add_argument("--debug", action="store_true")
a = ap.parse_args()

W = json.load(open(a.words))
segs_src = W["segments"] if isinstance(W, dict) and "segments" in W else W
words = []
for s in segs_src:
    for w in s.get("words", []):
        if "start" in w and "end" in w:
            words.append({"word": w.get("word", w.get("text", "")), "start": float(w["start"]), "end": float(w["end"])})
if not words:
    _sys.exit("no word-level timestamps in --words")
dur = words[-1]["end"]

prior = json.load(open(a.prior)); prior = prior["blocks"] if isinstance(prior, dict) else prior
def speaker_at(t):
    for b in prior:
        if b["start"] <= t < b["end"]:
            return b.get("shot", b.get("speaker", "host"))
    return prior[-1].get("shot", prior[-1].get("speaker", "host"))

segs = [{"speaker": speaker_at(0)}]
segdur = [(0.0, dur)]                          # mics pre-aligned: clip-time == mic-time
spk_mic = {"host": _os.path.abspath(a.host_mic), "guest": _os.path.abspath(a.guest_mic)}
guest, perword = resolve_speakers(words, segdur, segs, speaker_at, spk_mic, cam_dir=".", debug=a.debug)

# per-word labels -> blocks
blocks = []
for i, w in enumerate(words):
    sp = perword[i][0]
    if blocks and blocks[-1]["shot"] == sp:
        blocks[-1]["end"] = w["end"]
    else:
        blocks.append({"start": w["start"], "end": w["end"], "shot": sp})
# absorb sub-min-block flickers into the surrounding shot (hold through backchannels), then re-merge
out = []
for b in blocks:
    if out and (b["end"] - b["start"]) < a.min_block:
        out[-1]["end"] = b["end"]                          # too short to cut to -> hold prev shot
    elif out and out[-1]["shot"] == b["shot"]:
        out[-1]["end"] = b["end"]
    else:
        out.append(dict(b))
final = []
for b in out:
    if final and final[-1]["shot"] == b["shot"]:
        final[-1]["end"] = b["end"]
    else:
        final.append(dict(b))
# emit ABS time, contiguous
abs_blocks = [{"start": round(a.seg_start + b["start"], 3), "end": round(a.seg_start + b["end"], 3), "shot": b["shot"]} for b in final]
for i in range(len(abs_blocks) - 1):
    abs_blocks[i]["end"] = abs_blocks[i + 1]["start"]
abs_blocks[0]["start"] = round(a.seg_start, 3); abs_blocks[-1]["end"] = round(a.seg_start + dur, 3)
json.dump({"blocks": abs_blocks}, open(a.out, "w"), indent=1)
g = sum(1 for b in abs_blocks if b["shot"] == "guest")
print(f"[diarize] {len(abs_blocks)} blocks -> {a.out}  ({g} guest / {len(abs_blocks)-g} host)")
