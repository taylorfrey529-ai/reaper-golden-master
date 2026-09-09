#!/usr/bin/env bash
set -euo pipefail
for tool in Xvfb xauth xdpyinfo xwininfo scrot ss; do
  command -v "$tool" >/dev/null 2>&1 || {
    echo "display-88 TCP candidate blocked: missing required tool: $tool" >&2
    exit 75
  }
done
exec python3 "$(dirname "$0")/reaper-display88-tcp-candidate.py" acquire-candidate --display 88 "$@"
