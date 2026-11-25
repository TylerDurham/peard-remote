#!/usr/bin/env bash
# Install peard (editable, via uv tool), link the Noctalia plugin, and
# enable the systemd user service. Safe to re-run after pulling changes.
set -euo pipefail

action=INSTALL
dev_mode=0

while [[ "$#" -gt 0 ]]; do 
  case "$1" in 
    -d|--dev-mode) dev_mode=1; shift ;;
    -u|--uninstall) action=UNINSTALL; shift ;;
    *) shift ;;
  esac
done

here="$(cd "$(dirname "$0")" && pwd)"
plugins="${XDG_DATA_HOME:-$HOME/.local/share}/noctalia/plugins"
units="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"

install() {
  echo "installing"
  uv tool install --force --editable "$here/daemon"


  mkdir -p "$plugins" "$units"
  ln -sfn "$here/plugin" "$plugins/peard-remote"
  ln -sfn "$here/daemon/peard.service" "$units/peard.service"

  systemctl --user daemon-reload
  systemctl --user enable peard.service
  systemctl --user restart peard.service

  if pgrep -x noctalia >/dev/null; then
    noctalia msg plugins enable dtd/peard-remote || true
  fi
}

uninstall() {
  echo "uninstalling"

  systemctl --user stop peard.service
  systemctl --user disable peard.service
  rm -rf "$units/peard.service"
  systemctl --user daemon-reload

  rm -rf "$plugins/peard-remote"
  if pgrep -x noctalia >/dev/null; then
    noctalia msg plugins disable dtd/peard-remote || true
  fi

  uv tool uninstall "daemon"

}

case "$action" in 
  INSTALL) install ;;
  UNINSTALL) uninstall
esac

exit 0

uv tool install --force --editable "$here/daemon"

mkdir -p "$plugins" "$units"
ln -sfn "$here/plugin" "$plugins/peard-remote"
ln -sfn "$here/daemon/peard.service" "$units/peard.service"

systemctl --user daemon-reload
systemctl --user enable peard.service
systemctl --user restart peard.service

if pgrep -x noctalia >/dev/null; then
  noctalia msg plugins enable dtd/peard-remote || true
fi

cat <<'MSG'

Installed. Next:
  1. peard pair         # pick a TV and enter the PIN it shows; repeat per TV
  2. peard set-active   # choose which TV to control
  3. Add the widget to a bar in ~/.config/noctalia/config.toml:
       end = [ ..., "appletv", ... ]
       [widget.appletv]
       type = "dtd/peard-remote:remote"
MSG
