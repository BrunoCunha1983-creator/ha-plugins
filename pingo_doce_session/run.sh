#!/usr/bin/env bash
set -euo pipefail

export DISPLAY="${DISPLAY:-:99}"
mkdir -p /data/chromium-profile /data/session /config/pingo_doce_session /tmp/.X11-unix

DISPLAY_NUM="${DISPLAY#:}"
rm -f "/tmp/.X${DISPLAY_NUM}-lock" \
      /data/chromium-profile/SingletonCookie \
      /data/chromium-profile/SingletonLock \
      /data/chromium-profile/SingletonSocket

Xvfb "${DISPLAY}" -screen 0 1440x900x24 -ac +extension GLX +render -noreset > /tmp/xvfb.log 2>&1 &
XVFB_PID=$!

for _ in $(seq 1 50); do
  if [[ -S "/tmp/.X11-unix/X${DISPLAY_NUM}" ]]; then
    break
  fi
  sleep 0.2
done

openbox-session > /tmp/openbox.log 2>&1 &

VNC_PASSWORD="$(python - <<'PY'
import json
from pathlib import Path
try:
    data = json.loads(Path('/data/options.json').read_text(encoding='utf-8'))
except Exception:
    data = {}
print(str(data.get('vnc_password') or ''))
PY
)"

if [[ -n "${VNC_PASSWORD}" ]]; then
  x11vnc -storepasswd "${VNC_PASSWORD}" /data/session/vnc.pass >/dev/null
  x11vnc -display "${DISPLAY}" -rfbauth /data/session/vnc.pass -forever -shared \
    -rfbport 5900 -listen 127.0.0.1 -noxdamage > /tmp/x11vnc.log 2>&1 &
else
  x11vnc -display "${DISPLAY}" -nopw -forever -shared \
    -rfbport 5900 -listen 127.0.0.1 -noxdamage > /tmp/x11vnc.log 2>&1 &
fi

websockify --web=/usr/share/novnc/ 7900 127.0.0.1:5900 > /tmp/novnc.log 2>&1 &

python -m app.bridge &
BRIDGE_PID=$!

cleanup() {
  kill "${BRIDGE_PID}" "${XVFB_PID}" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

exec python -m app.main
