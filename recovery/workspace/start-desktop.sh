#!/usr/bin/env bash
set -euo pipefail
ROOT=/mnt/data/ubuntu-desktop-workspace
DISPLAY_NUM=${DISPLAY_NUM:-88}
export DISPLAY=:$DISPLAY_NUM
export HOME="$ROOT/home"
export XDG_CONFIG_HOME="$ROOT/config"
mkdir -p "$ROOT/run" "$ROOT/logs" "$HOME" "$ROOT/assets"

xvfb_pattern="^Xvfb :${DISPLAY_NUM} "
openbox_pattern="^openbox --config-file ${ROOT}/config/openbox/rc.xml$"
desktop_pattern="^python3 ${ROOT}/desktop_shell.py$"

existing_xvfb=$(pgrep -f "$xvfb_pattern" | head -n 1 || true)
if xdpyinfo -display "$DISPLAY" >/dev/null 2>&1; then
  if [ -z "$existing_xvfb" ]; then
    echo "Display $DISPLAY is reachable but is not owned by the expected Xvfb process." >&2
    exit 2
  fi
  echo "$existing_xvfb" > "$ROOT/run/xvfb.pid"
else
  if [ -n "$existing_xvfb" ]; then
    kill "$existing_xvfb" 2>/dev/null || true
    sleep 0.2
    kill -9 "$existing_xvfb" 2>/dev/null || true
  fi
  rm -f /tmp/.X${DISPLAY_NUM}-lock /tmp/.X11-unix/X${DISPLAY_NUM} 2>/dev/null || true
  Xvfb "$DISPLAY" -screen 0 1440x900x24 -nolisten tcp -ac >"$ROOT/logs/xvfb.log" 2>&1 &
  xvfb_pid=$!
  echo "$xvfb_pid" > "$ROOT/run/xvfb.pid"
  ready=0
  for _ in $(seq 1 50); do
    if kill -0 "$xvfb_pid" 2>/dev/null && xdpyinfo -display "$DISPLAY" >/dev/null 2>&1; then ready=1; break; fi
    sleep 0.1
  done
  if [ "$ready" -ne 1 ]; then
    echo "Xvfb failed to become ready on $DISPLAY" >&2
    exit 3
  fi
fi

openbox_pid=$(pgrep -f "$openbox_pattern" | head -n 1 || true)
if [ -z "$openbox_pid" ]; then
  openbox --config-file "$ROOT/config/openbox/rc.xml" >"$ROOT/logs/openbox.log" 2>&1 &
  openbox_pid=$!
  sleep 0.4
fi
echo "$openbox_pid" > "$ROOT/run/openbox.pid"

desktop_pid=$(pgrep -f "$desktop_pattern" | head -n 1 || true)
if [ -z "$desktop_pid" ]; then
  python3 "$ROOT/desktop_shell.py" >"$ROOT/logs/desktop-shell.log" 2>&1 &
  desktop_pid=$!
fi
echo "$desktop_pid" > "$ROOT/run/desktop-shell.pid"

for _ in $(seq 1 60); do
  if kill -0 "$desktop_pid" 2>/dev/null && DISPLAY="$DISPLAY" xwininfo -root -tree 2>/dev/null | grep -q '"Ubuntu Workspace Desktop"'; then
    echo "$DISPLAY" > "$ROOT/run/display"
    echo "Ubuntu workspace desktop started on $DISPLAY"
    exit 0
  fi
  sleep 0.15
done

echo 'Desktop shell did not become ready.' >&2
exit 1
