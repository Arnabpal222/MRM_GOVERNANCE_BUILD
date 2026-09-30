#!/usr/bin/env bash
# Copy files to <root>/_OLD/<relative dir>/<name>_v<N>_<YYYYMMDD>.<ext> before they are edited.
# Usage (from project root):  bash A_Codes/AZ_tools/snapshot.sh A_Codes AB_backend/app/main.py [more paths...]
set -euo pipefail
root=$1; shift
for rel in "$@"; do
  dir=$(dirname "$rel"); base=$(basename "$rel")
  if [[ "$base" == .* && "${base:1}" != *.* ]] || [[ "$base" != *.* ]]; then
    name="$base"; ext=""   # dotfiles (.gitignore) and extension-less files
  else
    name="${base%.*}"; ext=".${base##*.}"
  fi
  dest="$root/_OLD"; [ "$dir" != "." ] && dest="$dest/$dir"
  mkdir -p "$dest"
  n=1; while ls "$dest/${name}_v${n}_"*"$ext" >/dev/null 2>&1; do n=$((n+1)); done
  cp "$root/$rel" "$dest/${name}_v${n}_$(date +%Y%m%d)$ext"
  echo "saved $dest/${name}_v${n}_$(date +%Y%m%d)$ext"
done
