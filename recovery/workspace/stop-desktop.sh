#!/usr/bin/env bash
set -euo pipefail
ROOT=/mnt/data/ubuntu-desktop-workspace
DISPLAY_NUM=${DISPLAY_NUM:-88}

kill_pid() {
  local p=${1:-}
  [ -n "$p" ] || return 0
  kill "$p" 2>/dev/null || true
}
kill_pid_hard() {
  local p=${1:-}
  [ -n "$p" ] || return 0
  kill -9 "$p" 2>/dev/null || true
}

for f in desktop-shell.pid openbox.pid xvfb.pid; do
  if [ -f "$ROOT/run/$f" ]; then kill_pid "$(cat "$ROOT/run/$f" 2>/dev/null || true)"; fi
done

# PID files are advisory; also stop only exact workspace/display processes.
for pattern in \
  "^python3 ${ROOT}/desktop_shell.py$" \
  "^openbox --config-file ${ROOT}/config/openbox/rc.xml$" \
  "^Xvfb :${DISPLAY_NUM} "; do
  while read -r p; do [ -n "$p" ] && kill_pid "$p"; done < <(pgrep -f "$pattern" || true)
done

sleep 0.3
for f in desktop-shell.pid openbox.pid xvfb.pid; do
  if [ -f "$ROOT/run/$f" ]; then kill_pid_hard "$(cat "$ROOT/run/$f" 2>/dev/null || true)"; fi
done
for pattern in \
  "^python3 ${ROOT}/desktop_shell.py$" \
  "^openbox --config-file ${ROOT}/config/openbox/rc.xml$" \
  "^Xvfb :${DISPLAY_NUM} "; do
  while read -r p; do [ -n "$p" ] && kill_pid_hard "$p"; done < <(pgrep -f "$pattern" || true)
done

rm -f "$ROOT/run/"*.pid "$ROOT/run/display" /tmp/.X${DISPLAY_NUM}-lock /tmp/.X11-unix/X${DISPLAY_NUM} 2>/dev/null || true
