#!/usr/bin/env bash
set -euo pipefail
exec python3 "$(dirname "$0")/reaper-display88ctl.py" --display 88 acquire "$@"
