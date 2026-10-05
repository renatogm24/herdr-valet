#!/usr/bin/env bash
# Instala herdr-valet para el usuario actual: el comando `herdr-valet`, la config y dos
# servicios de usuario (systemd en Linux, launchd en macOS):
#   - auto: cada 10 min, foto de lo abierto + aparca lo quieto hace más de idle_days
#   - web:  la página, en 127.0.0.1:<port>
#
#   ./install.sh               instala o actualiza (re-correrlo después de un git pull)
#   ./install.sh --uninstall   saca los servicios y el comando; las fichas y la config quedan
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN="$HOME/.local/bin/herdr-valet"
CONF_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/herdr-valet"
# Los servicios no heredan el PATH del shell: herdr y claude tienen que estar en alguno de estos.
SVC_PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
OS="$(uname -s)"

say() { printf '  %s\n' "$*"; }

# Python 3.9 o más nuevo: el de Apple (Command Line Tools) es 3.9 y alcanza.
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
# herdr-valet ($DIR): foto de lo abierto + aparca lo quieto. Lo dispara herdr-valet-auto.timer.
[Unit]
Description=herdr-valet: aparcar sesiones quietas

[Service]
Type=oneshot
Environment=PATH=$SVC_PATH
ExecStart=$PY $DIR/valet.py auto
EOF
  cat >"$d/herdr-valet-auto.timer" <<EOF
# Cada 10 minutos y 3 después de arrancar (recupera lo que cortó un reinicio). Con nada que
# aparcar dura menos de un segundo.
[Unit]
Description=herdr-valet: aparcar sesiones quietas (cada 10 min)

[Timer]
OnBootSec=3min
OnCalendar=*:0/10
RandomizedDelaySec=60
Persistent=true

[Install]
WantedBy=timers.target
EOF
  cat >"$d/herdr-valet-web.service" <<EOF
# herdr-valet ($DIR): la página de sesiones aparcadas.
[Unit]
Description=herdr-valet: página de sesiones aparcadas

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
  # restart y no solo start: un git pull que cambia la página tiene que verse sin pasos extra.
  systemctl --user enable herdr-valet-web.service >/dev/null
  systemctl --user restart herdr-valet-web.service
  say "✓ systemd: herdr-valet-auto.timer y herdr-valet-web.service"
  loginctl show-user "$USER" -p Linger 2>/dev/null | grep -q yes \
    || say "! Sin linger los servicios solo corren con tu sesión abierta: sudo loginctl enable-linger $USER"
}

systemd_uninstall() {
  systemctl --user disable --now herdr-valet-auto.timer herdr-valet-web.service >/dev/null 2>&1 || true
  rm -f "$HOME/.config/systemd/user"/herdr-valet-{auto.service,auto.timer,web.service}
  systemctl --user daemon-reload
  say "✓ servicios de systemd sacados"
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
  say "✓ launchd: dev.herdr-valet.auto (cada 10 min) y dev.herdr-valet.web (logs en $LOGS)"
}

launchd_uninstall() {
  for l in dev.herdr-valet.auto dev.herdr-valet.web; do
    launchctl bootout "gui/$(id -u)/$l" 2>/dev/null || true
    rm -f "$LA/$l.plist"
  done
  say "✓ servicios de launchd sacados"
}

# --------------------------------------------------------------------------- main
if [ "${1:-}" = "--uninstall" ]; then
  case "$OS" in Darwin) launchd_uninstall ;; Linux) systemd_uninstall ;; esac
  rm -f "$BIN"
  say "✓ listo. Fichas y config quedan en ~/.local/share/herdr-valet y $CONF_DIR"
  exit 0
fi

echo "herdr-valet"
[ -n "$PY" ] || { say "✗ falta Python 3.9 o más nuevo"; exit 1; }
command -v herdr >/dev/null || say "! herdr no está en el PATH (https://herdr.dev)"
command -v claude >/dev/null || say "! claude no está en el PATH: sin él no hay resúmenes ni reanudar"

chmod +x "$DIR/valet.py" "$DIR/web.py"
mkdir -p "$(dirname "$BIN")"
ln -sf "$DIR/valet.py" "$BIN"
say "✓ comando: $BIN"

if [ ! -f "$CONF_DIR/config.toml" ]; then
  mkdir -p "$CONF_DIR"
  cp "$DIR/config.example.toml" "$CONF_DIR/config.toml"
  say "✓ config: $CONF_DIR/config.toml"
fi
"$PY" "$DIR/valet.py" config >/dev/null || { say "✗ la config tiene un error"; exit 1; }

case "$OS" in
  Darwin) launchd_install ;;
  Linux)
    if command -v systemctl >/dev/null && systemctl --user show-environment >/dev/null 2>&1; then
      systemd_install
    else
      say "- sin systemd de usuario: corré 'herdr-valet auto' y 'web.py' como prefieras"
    fi
    ;;
  *) say "- $OS: sin servicios; corré 'herdr-valet auto' y 'web.py' como prefieras" ;;
esac

port="$("$PY" "$DIR/valet.py" config | sed -n 's/^port = //p')"
say "✓ página: http://127.0.0.1:$port"
