#!/usr/bin/env python3
"""Rank audio tracks by 'upbeat' = tempo (BPM) + energy (RMS). Brand music-selection helper.

USE WHEN the music ask is about ENERGY ("more upbeat" / "higher energy" / "too chill/slow") —
measurement is your ears for the energy axis (you can't audition tracks in-session). Vibe-by-name
works for FEEL but fails for ENERGY; measure instead of guessing.

  measure_tempo.py track1.mp3 track2.mp3 ...        # specific tracks
  measure_tempo.py "/path/to/(1) Tik Tok/(1) Calm"  # whole folder
ALWAYS include the current/rejected track as a baseline to compare against.

Measured reference points: chill bed ~107 BPM/0.10 · smooth-mid ~129/0.22 · upbeat ~135-155/0.30+.
(needs: pip install --break-system-packages librosa)"""
import os, sys, glob
import numpy as np
try:
    import librosa
except ImportError:
    sys.exit("librosa missing -> pip install --break-system-packages librosa")

args = sys.argv[1:]
if not args:
    sys.exit(__doc__)
files = []
for a in args:
    files += sorted(glob.glob(os.path.join(a, "*.mp3"))) if os.path.isdir(a) else [a]

res = []
for p in files:
    try:
        y, sr = librosa.load(p, offset=20, duration=45, mono=True)
        try:
            tempo = float(librosa.beat.beat_track(y=y, sr=sr)[0])
        except Exception:
            tempo = float(np.atleast_1d(librosa.feature.tempo(y=y, sr=sr))[0])
        rms = float(np.mean(librosa.feature.rms(y=y)))
        res.append((tempo, rms, os.path.basename(p)))
    except Exception as e:
        print("ERR", os.path.basename(p), e)

print("\n=== ranked by tempo (BPM) | energy (RMS) ===")
print("ref: chill~107/0.10  mid~129/0.22  upbeat~135-155/0.30+  (high BPM + low energy != upbeat)")
for t, r, n in sorted(res, reverse=True):
    print(f"{t:6.1f} BPM   {r:.3f}   {n}")
