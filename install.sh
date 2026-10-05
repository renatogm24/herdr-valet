#!/usr/bin/env bash
# Installs herdr-valet for the current user: the `herdr-valet` command, the config and two user
# services (systemd on Linux, launchd on macOS):
#   - auto: every 10 min, snapshot what is open + park sessions idle for more than idle_days
#   - web:  the page, on 127.0.0.1:<port>
#
#   ./install.sh               install or update (re-run it after a git pull)
#   ./install.sh --uninstall   remove the services and the command; cards and config stay
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN="$HOME/.local/bin/herdr-valet"
CONF_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/herdr-valet"
# Services don't inherit the shell's PATH: herdr and claude must live in one of these.
SVC_PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
OS="$(uname -s)"

say() { printf '  %s\n' "$*"; }

# Python 3.9 or newer: Apple's (Command Line Tools) is 3.9, which is enough.
PY=""
for c in python3.13 python3.12 python3.11 python3.10 python3; do
  p="$(command -v "$c" 2>/dev/null)" || continue
  "$p" -c 'import sys; sys.exit(sys.version_info < (3, 9))' 2>/dev/null && { PY="$p"; break; }
done

# --------------------------------------------------------------------------- Linux
systemd_install() {
  local d="$HOME/.config/systemd/user"
  mkdir -p "$d"
  cat >"$d/herdr-valet-auto.service" <<EOF
# herdr-valet ($DIR): snapshot what is open + park idle sessions. Fired by herdr-valet-auto.timer.
[Unit]
Description=herdr-valet: park idle sessions

[Service]
Type=oneshot
Environment=PATH=$SVC_PATH
ExecStart=$PY $DIR/valet.py auto
EOF
  cat >"$d/herdr-valet-auto.timer" <<EOF
# Every 10 minutes and 3 after boot (recovers what a reboot cut off). With nothing to park it
# takes under a second.
[Unit]
Description=herdr-valet: park idle sessions (every 10 min)

[Timer]
OnBootSec=3min
OnCalendar=*:0/10
RandomizedDelaySec=60
Persistent=true

[Install]
WantedBy=timers.target
EOF
  cat >"$d/herdr-valet-web.service" <<EOF
# herdr-valet ($DIR): the parked sessions page.
[Unit]
Description=herdr-valet: parked sessions page

[Service]
Environment=PATH=$SVC_PATH
ExecStart=$PY $DIR/web.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF
  systemctl --user daemon-reload
  systemctl --user enable --now herdr-valet-auto.timer >/dev/null
  # restart, not just start: a git pull that changes the page must show up with no extra step.
  systemctl --user enable herdr-valet-web.service >/dev/null
  systemctl --user restart herdr-valet-web.service
  say "✓ systemd: herdr-valet-auto.timer and herdr-valet-web.service"
  loginctl show-user "$USER" -p Linger 2>/dev/null | grep -q yes \
    || say "! Without linger the services only run while you are logged in: sudo loginctl enable-linger $USER"
}

systemd_uninstall() {
  systemctl --user disable --now herdr-valet-auto.timer herdr-valet-web.service >/dev/null 2>&1 || true
  rm -f "$HOME/.config/systemd/user"/herdr-valet-{auto.service,auto.timer,web.service}
  systemctl --user daemon-reload
  say "✓ systemd services removed"
}

# --------------------------------------------------------------------------- macOS
LA="$HOME/Library/LaunchAgents"
LOGS="$HOME/Library/Logs/herdr-valet"

plist() { # label, script, extra keys
  cat >"$LA/$1.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$1</string>
  <key>ProgramArguments</key>
  <array><string>$PY</string>$2</array>
  <key>EnvironmentVariables</key>
  <dict><key>PATH</key><string>$SVC_PATH</string></dict>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>$LOGS/$1.log</string>
  <key>StandardErrorPath</key><string>$LOGS/$1.log</string>
$3
</dict>
</plist>
EOF
  launchctl bootout "gui/$(id -u)/$1" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" "$LA/$1.plist"
}

launchd_install() {
  mkdir -p "$LA" "$LOGS"
  plist dev.herdr-valet.auto "<string>$DIR/valet.py</string><string>auto</string>" \
    "  <key>StartInterval</key><integer>600</integer>"
  plist dev.herdr-valet.web "<string>$DIR/web.py</string>" \
    "  <key>KeepAlive</key><true/>"
  say "✓ launchd: dev.herdr-valet.auto (every 10 min) and dev.herdr-valet.web (logs in $LOGS)"
}

launchd_uninstall() {
  for l in dev.herdr-valet.auto dev.herdr-valet.web; do
    launchctl bootout "gui/$(id -u)/$l" 2>/dev/null || true
    rm -f "$LA/$l.plist"
  done
  say "✓ launchd services removed"
}

# --------------------------------------------------------------------------- main
if [ "${1:-}" = "--uninstall" ]; then
  case "$OS" in Darwin) launchd_uninstall ;; Linux) systemd_uninstall ;; esac
  rm -f "$BIN"
  say "✓ done. Cards and config stay in ~/.local/share/herdr-valet and $CONF_DIR"
  exit 0
fi

echo "herdr-valet"
[ -n "$PY" ] || { say "✗ Python 3.9 or newer is required"; exit 1; }
command -v herdr >/dev/null || say "! herdr is not on PATH (https://herdr.dev)"
command -v claude >/dev/null || say "! claude is not on PATH: without it there are no summaries and no resume"

chmod +x "$DIR/valet.py" "$DIR/web.py"
mkdir -p "$(dirname "$BIN")"
ln -sf "$DIR/valet.py" "$BIN"
say "✓ command: $BIN"

if [ ! -f "$CONF_DIR/config.toml" ]; then
  mkdir -p "$CONF_DIR"
  cp "$DIR/config.example.toml" "$CONF_DIR/config.toml"
  say "✓ config: $CONF_DIR/config.toml"
fi
"$PY" "$DIR/valet.py" config >/dev/null || { say "✗ the config has an error"; exit 1; }

case "$OS" in
  Darwin) launchd_install ;;
  Linux)
    if command -v systemctl >/dev/null && systemctl --user show-environment >/dev/null 2>&1; then
      systemd_install
    else
      say "- no systemd user session: run 'herdr-valet auto' and 'web.py' however you prefer"
    fi
    ;;
  *) say "- $OS: no services; run 'herdr-valet auto' and 'web.py' however you prefer" ;;
esac

port="$("$PY" "$DIR/valet.py" config | sed -n 's/^port = //p')"
say "✓ page: http://127.0.0.1:$port"
