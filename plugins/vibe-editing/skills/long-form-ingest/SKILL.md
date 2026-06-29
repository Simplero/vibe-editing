---
name: long-form-ingest
description: Transcribe a long-form video to word-level timestamped JSON and detect scene boundaries. Use whenever a new video file enters the pipeline and a transcript does not yet exist. Produces transcript.json (word-level with timestamps), scenes.json (visual cut points), and meta.json (duration, fps, resolution). Every other video skill depends on these outputs.
---

# Long-Form Ingest

Extract three artifacts from a raw video:
1. `transcript.json` — word-level timestamps from faster-whisper
2. `scenes.json` — visual scene boundaries from PySceneDetect
3. `meta.json` — video technical metadata

All outputs go to `./out/<source-basename>/`.

## Workflow

```bash
# 1. Metadata
ffprobe -v quiet -print_format json -show_format -show_streams "$INPUT" > meta.json

# 2. Extract audio (mono 16kHz for Whisper)
ffmpeg -y -i "$INPUT" -ac 1 -ar 16000 -vn _staging/audio.wav

# 3. Transcribe with faster-whisper (word-level)
python scripts/transcribe.py _staging/audio.wav transcript.json

# 4. Scene detection (optional but cheap — skip for pure talking-head if user says --no-scenes)
python scripts/scenes.py "$INPUT" scenes.json
```

## transcript.json schema

```json
{
  "language": "en",
  "duration": 2534.12,
  "segments": [
    {
      "id": 0,
      "start": 0.32,
      "end": 8.74,
      "text": " So this one time I got a call from a founder who was convinced his SaaS was dying.",
      "words": [
        {"word": " So", "start": 0.32, "end": 0.48, "probability": 0.99},
        {"word": " this", "start": 0.48, "end": 0.63, "probability": 0.98},
        ...
      ]
    }
  ]
}
```

## scenes.json schema

```json
{
  "scenes": [
    {"start": 0.0, "end": 128.4, "type": "static"},
    {"start": 128.4, "end": 245.1, "type": "cut"}
  ]
}
```

## scripts/transcribe.py

```python
#!/usr/bin/env python3
import sys, json
from faster_whisper import WhisperModel

audio_path, out_path = sys.argv[1], sys.argv[2]

# large-v3 for quality. Use "medium" if GPU-poor.
model = WhisperModel("large-v3", device="auto", compute_type="auto",
                     download_root="~/.cache/whisper-models")

segments, info = model.transcribe(
    audio_path,
    word_timestamps=True,
    vad_filter=True,
    vad_parameters={"min_silence_duration_ms": 500}
)

out = {
    "language": info.language,
    "duration": info.duration,
    "segments": []
}

for i, seg in enumerate(segments):
    out["segments"].append({
        "id": i,
        "start": seg.start,
        "end": seg.end,
        "text": seg.text,
        "words": [
            {"word": w.word, "start": w.start, "end": w.end, "probability": w.probability}
            for w in (seg.words or [])
        ]
    })

with open(out_path, "w") as f:
    json.dump(out, f, indent=2)

print(f"Transcribed {info.duration:.1f}s in {len(out['segments'])} segments")
```

## scripts/scenes.py

```python
#!/usr/bin/env python3
import sys, json
from scenedetect import detect, ContentDetector

video_path, out_path = sys.argv[1], sys.argv[2]
scene_list = detect(video_path, ContentDetector(threshold=27.0))

out = {
    "scenes": [
        {"start": s[0].get_seconds(), "end": s[1].get_seconds(), "type": "cut"}
        for s in scene_list
    ]
}

# If no scenes detected, treat whole video as one
if not out["scenes"]:
    import subprocess
    dur = float(subprocess.check_output([
        "ffprobe", "-v", "quiet", "-show_entries", "format=duration",
        "-of", "csv=p=0", video_path
    ]).decode().strip())
    out["scenes"] = [{"start": 0.0, "end": dur, "type": "static"}]

with open(out_path, "w") as f:
    json.dump(out, f, indent=2)

print(f"Found {len(out['scenes'])} scenes")
```

## Defaults

- Whisper model: `large-v3` (best quality for podcast speech). Fallback to `medium` if VRAM < 6GB.
- VAD filter: on, with 500ms silence threshold (prevents hallucinating words in gaps).
- Scene threshold: 27.0 (PySceneDetect default, good for talking head).

## Performance

- 1hr audio on M2 Pro with `large-v3`: ~6 minutes
- 1hr audio on CPU (no GPU): ~25 minutes
- Scene detection 1hr video: ~2 minutes

## Health-check

```bash
python -c "from faster_whisper import WhisperModel; print('ok')"
python -c "from scenedetect import detect; print('ok')"
ffmpeg -version | head -1
ffprobe -version | head -1
```

All four must succeed.

## Edge cases

- **Non-English audio:** faster-whisper auto-detects. If the user's audio is multilingual, set `language="en"` explicitly to force.
- **Very long files (>3hr):** chunk into 30-min segments and stitch transcripts with offset correction.
- **Background music:** VAD handles it mostly; if noisy, pre-process with `ffmpeg -af "highpass=f=200,lowpass=f=3000"`.
- **No speech detected:** fail loudly with a clear error. Don't produce an empty transcript silently.
