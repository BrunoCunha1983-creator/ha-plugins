#!/usr/bin/env bash
set -Eeuo pipefail

export DISPLAY="${DISPLAY:-:99}"
DISPLAY_NUM="${DISPLAY#:}"

mkdir -p /data/chromium-profile /data/session /homeassistant/pingo_doce_plus /tmp/.X11-unix
chmod 1777 /tmp/.X11-unix
rm -f "/tmp/.X${DISPLAY_NUM}-lock" \
      "/tmp/.X11-unix/X${DISPLAY_NUM}" \
      /data/chromium-profile/SingletonCookie \
      /data/chromium-profile/SingletonLock \
      /data/chromium-profile/SingletonSocket

log() {
  printf '[Pingo Doce Plus] %s\n' "$*"
}

show_log_and_exit() {
  local name="$1"
  local file="$2"
  log "Falha ao iniciar ${name}."
  [[ -f "${file}" ]] && tail -n 100 "${file}" || true
  exit 1
}

cleanup() {
  for pid in "${WEBSOCKIFY_PID:-}" "${VNC_PID:-}" "${OPENBOX_PID:-}" "${XVFB_PID:-}"; do
    [[ -n "${pid}" ]] && kill "${pid}" 2>/dev/null || true
  done
}
trap cleanup EXIT INT TERM

log "A iniciar servidor gráfico Xvfb em ${DISPLAY}"
Xvfb "${DISPLAY}" -screen 0 1440x900x24 -ac +extension GLX +render -noreset \
  > /tmp/xvfb.log 2>&1 &
XVFB_PID=$!

for _ in $(seq 1 100); do
  kill -0 "${XVFB_PID}" 2>/dev/null || show_log_and_exit "Xvfb" /tmp/xvfb.log
  [[ -S "/tmp/.X11-unix/X${DISPLAY_NUM}" ]] && break
  sleep 0.1
done
[[ -S "/tmp/.X11-unix/X${DISPLAY_NUM}" ]] || show_log_and_exit "Xvfb" /tmp/xvfb.log

log "A iniciar Openbox"
dbus-run-session -- openbox-session > /tmp/openbox.log 2>&1 &
OPENBOX_PID=$!

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

VNC_ARGS=(
  -display "${DISPLAY}"
  -forever
  -shared
  -repeat
  -noxdamage
  -xkb
  -rfbport 5900
  -listen 127.0.0.1
)

if [[ -n "${VNC_PASSWORD}" ]]; then
  x11vnc -storepasswd "${VNC_PASSWORD}" /data/session/vnc.pass >/dev/null
  chmod 600 /data/session/vnc.pass
  VNC_ARGS+=( -rfbauth /data/session/vnc.pass )
else
  VNC_ARGS+=( -nopw )
fi

log "A iniciar x11vnc"
x11vnc "${VNC_ARGS[@]}" > /tmp/x11vnc.log 2>&1 &
VNC_PID=$!

for _ in $(seq 1 100); do
  kill -0 "${VNC_PID}" 2>/dev/null || show_log_and_exit "x11vnc" /tmp/x11vnc.log
  if (echo > /dev/tcp/127.0.0.1/5900) >/dev/null 2>&1; then
    break
  fi
  sleep 0.1
done
if ! (echo > /dev/tcp/127.0.0.1/5900) >/dev/null 2>&1; then
  show_log_and_exit "x11vnc" /tmp/x11vnc.log
fi

NOVNC_WEB="/usr/share/novnc"
if [[ ! -f "${NOVNC_WEB}/vnc.html" ]]; then
  NOVNC_WEB="$(find /usr/share -type f -path '*/novnc/vnc.html' -printf '%h\n' -quit 2>/dev/null || true)"
fi
[[ -n "${NOVNC_WEB}" && -f "${NOVNC_WEB}/vnc.html" ]] || show_log_and_exit "noVNC" /tmp/novnc.log

log "A iniciar noVNC na porta 7900"
websockify --heartbeat=30 --web="${NOVNC_WEB}" 0.0.0.0:7900 127.0.0.1:5900 \
  > /tmp/novnc.log 2>&1 &
WEBSOCKIFY_PID=$!

for _ in $(seq 1 100); do
  kill -0 "${WEBSOCKIFY_PID}" 2>/dev/null || show_log_and_exit "websockify/noVNC" /tmp/novnc.log
  if (echo > /dev/tcp/127.0.0.1/7900) >/dev/null 2>&1; then
    break
  fi
  sleep 0.1
done
if ! (echo > /dev/tcp/127.0.0.1/7900) >/dev/null 2>&1; then
  show_log_and_exit "websockify/noVNC" /tmp/novnc.log
fi

log "noVNC pronto em http://HOST:7900/vnc.html"
exec python -m app.main
