#!/usr/bin/env bash
set -euo pipefail
ROOT=/mnt/data/ubuntu-desktop-workspace
CTL="$ROOT/reaper-display88ctl.py"
WRAP="$ROOT/acquire-display-88.sh"
HANDOFF="$ROOT/handoff/display-88"
expected_ctl=772a50e1a3e27a5016c12c6125e009da92bf286b1c92b1866c6d085203723b57
expected_wrap=e00213491b037c6462f90fa3034bab10464789ef6b12e61a2f277acb2f44e6d3
for pair in "$CTL:$expected_ctl" "$WRAP:$expected_wrap"; do
  path=${pair%%:*}; expected=${pair#*:}
  [ -f "$path" ] && [ ! -L "$path" ] || { echo "rollback-display88: missing or symlink: $path" >&2; exit 2; }
  actual=$(sha256sum "$path" | awk '{print $1}')
  [ "$actual" = "$expected" ] || { echo "rollback-display88: drift: $path" >&2; exit 3; }
done
rm -f "$WRAP" "$CTL"
rm -rf "$HANDOFF"
echo 'rollback-display88: PASS controller/wrapper/handoff removed; display processes untouched'
