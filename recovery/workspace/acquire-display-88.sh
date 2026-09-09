#!/usr/bin/env bash
set -euo pipefail
exec python3 "$(dirname "$0")/reaper-display88ctl.py" \
  --display 88 \
  --handoff-root /mnt/data/ubuntu-desktop-workspace/handoff/display-88 \
  acquire "$@"
