#!/usr/bin/env bash
set -euo pipefail

APP_ID="com.github.wwmm.easyeffects"
UID_NOW="$(id -u)"
PID="$(pgrep -n -u "$UID_NOW" -x plasmashell || true)"

if [[ -z "$PID" || ! -r "/proc/$PID/environ" ]]; then
  echo "plasmashell environment is not available" >&2
  exit 75
fi

# A systemd --user service survives session transitions, but its manager
# environment is not guaranteed to contain the current Plasma Wayland socket.
# Import the live plasmashell environment directly so EasyEffects is a real KDE
# graphical application with a functional StatusNotifier tray icon.
while IFS= read -r -d '' entry; do
  case "$entry" in
    WAYLAND_DISPLAY=*|DISPLAY=*|XDG_SESSION_TYPE=*|XDG_CURRENT_DESKTOP=*|DESKTOP_SESSION=*|KDE_FULL_SESSION=*|KDE_SESSION_VERSION=*|QT_WAYLAND_RECONNECT=*)
      export "$entry"
      ;;
  esac
done < "/proc/$PID/environ"

export HOME="/home/deck"
export USER="deck"
export LOGNAME="deck"
export XDG_RUNTIME_DIR="/run/user/$UID_NOW"
export DBUS_SESSION_BUS_ADDRESS="unix:path=$XDG_RUNTIME_DIR/bus"
export QT_QPA_PLATFORM="wayland"

exec /usr/bin/flatpak run --command=easyeffects "$APP_ID" --service-mode --hide-window
