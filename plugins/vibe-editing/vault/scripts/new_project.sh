#!/usr/bin/env bash
# new_project.sh — scaffold a dated job folder (00_SOURCE / 10_WORK / 20_DELIVER).
#   new_project.sh <group> <slug> [YYYY-MM-DD]  ->  ~/<OUTPUT>/<group>/<date>_<slug>/
#   new_project.sh <slug>                        ->  ~/<OUTPUT>/_PROJECTS/<date>_<slug>/
# "group" is any top-level folder to organize jobs (client/channel/brand); default "mybrand".
# Output root defaults to ~/Downloads; override with OUTPUT_DIR.
set -euo pipefail
DL="${OUTPUT_DIR:-$HOME/Downloads}"
if [ "$#" -lt 1 ]; then
  echo "usage: $(basename "$0") <group> <slug> [YYYY-MM-DD]" >&2; exit 1
fi
if [ "$#" -eq 1 ]; then
  group=""; slug="$1"; date_str="$(date +%Y-%m-%d)"; base="$DL/_PROJECTS"
else
  group="$1"; slug="$2"; date_str="${3:-$(date +%Y-%m-%d)}"
  if [ ! -d "$DL/$group" ]; then
    match="$(find "$DL" -maxdepth 1 -mindepth 1 -type d -iname "$group" 2>/dev/null | head -1)"
    [ -n "$match" ] && group="${match##*/}"
  fi
  base="$DL/$group"
fi
job="${date_str}_${slug}"; dir="$base/$job"
if [ -d "$dir" ]; then echo "exists: $dir" >&2; echo "$dir"; exit 0; fi
mkdir -p "$dir/00_SOURCE" "$dir/10_WORK" "$dir/20_DELIVER"
printf '# %s\n\n- group: %s\n- created: %s\n- status: intake\n' "$job" "${group:-_PROJECTS}" "$date_str" > "$dir/_project.md"
echo "created: $dir" >&2; echo "$dir"
