#!/usr/bin/env bash
set -euo pipefail
TARGET=/usr/local/bin/reaper-workspace-status
EXPECTED=${1:?expected installed sha256 required}
if [ ! -f "$TARGET" ] || [ -L "$TARGET" ]; then
  echo "rollback: target missing or not a regular non-symlink file" >&2
  exit 2
fi
CURRENT=$(sha256sum "$TARGET" | awk '{print $1}')
if [ "$CURRENT" != "$EXPECTED" ]; then
  echo "rollback: target changed; refusing delete" >&2
  exit 4
fi
rm -- "$TARGET"
[ ! -e "$TARGET" ] || { echo "rollback: deletion failed" >&2; exit 5; }
echo "rollback: restored pre-state (absent)"
