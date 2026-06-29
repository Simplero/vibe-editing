#!/bin/bash
# Brand FAST-RENDER — emit ffmpeg video encoder args for bash callers.
# Mirrors _shared/fast_encode.py for shell scripts. Use in any pipeline .sh:
#
#   read -ra ENC < <(bash "${CLAUDE_PLUGIN_ROOT}/lib/_shared/encode_args.sh" 2160 3840 delivery)
#   ffmpeg ... "${ENC[@]}" -c:a aac -b:a 320k out.mp4
#
# Args: WIDTH HEIGHT [TIER]    TIER = delivery (default) | intermediate | proxy | master
# Honors VIBE_ENCODER / VIBE_FAST env vars (same as the Python helper).
W=${1:?width}
H=${2:?height}
TIER=${3:-delivery}
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"   # this script lives in lib/_shared
python3 - "$HERE" <<PY
import sys
sys.path.insert(0, sys.argv[1])
from fast_encode import encoder_args
print(" ".join(encoder_args($W, $H, "ffmpeg", tier="$TIER")))
PY
