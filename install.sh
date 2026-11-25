#!/usr/bin/env bash
# Install peard (via uv tool) and the Noctalia plugin, and enable the systemd
# user service. Safe to re-run after pulling changes, or to switch modes.
#
#   (default)        copy the files, so this folder isn't needed afterwards
#   -d, --dev-mode   link to the files in this folder, so edits take effect
#   -u, --uninstall  remove everything except the saved config
set -euo pipefail

action=INSTALL
dev_mode=0

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    -d|--dev-mode) dev_mode=1; shift ;;
    -u|--uninstall) action=UNINSTALL; shift ;;
    *) echo "Unknown option: $1" >&2; echo "Usage: $0 [-d|--dev-mode] [-u|--uninstall]" >&2; exit 2 ;;
  esac
done

here="$(cd "$(dirname "$0")" && pwd)"
plugins="${XDG_DATA_HOME:-$HOME/.local/share}/noctalia/plugins"
units="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"

install() {
  mkdir -p "$plugins" "$units"

  if [[ "$dev_mode" -eq 1 ]]; then
    echo "installing (linked to $here)"
    uv tool install --force --editable "$here/daemon"
  else
    echo "installing"
    uv tool install --force "$here/daemon"
  fi

  # Remove what an earlier install left first. Copying over its links would write
  # into the folder they point to, and linking over a folder would link inside it.
  rm -rf "$plugins/peard-remote" "$units/peard.service"

  if [[ "$dev_mode" -eq 1 ]]; then
    ln -s "$here/plugin" "$plugins/peard-remote"
    ln -s "$here/daemon/peard.service" "$units/peard.service"
  else
    cp -r "$here/plugin" "$plugins/peard-remote"
    cp "$here/daemon/peard.service" "$units/peard.service"
  fi

  systemctl --user daemon-reload
  systemctl --user enable peard.service
  systemctl --user restart peard.service

  if pgrep -x noctalia >/dev/null; then
    noctalia msg plugins enable dtd/peard-remote || true
  fi

  cat <<'MSG'

Installed. Next:
  1. peard pair         # pick a TV and enter the PIN it shows; repeat per TV
  2. Add the widget to a bar in ~/.config/noctalia/config.toml:
       end = [ ..., "appletv", ... ]
       [widget.appletv]
       type = "dtd/peard-remote:remote"

To switch between TVs, use the picker in the remote or run: peard set-active
MSG
}

uninstall() {
  echo "uninstalling"

  # The service may already be gone, so keep cleaning up if these fail.
  systemctl --user stop peard.service || true
  systemctl --user disable peard.service || true
  rm -rf "$units/peard.service"
  systemctl --user daemon-reload

  rm -rf "$plugins/peard-remote"
  if pgrep -x noctalia >/dev/null; then
    noctalia msg plugins disable dtd/peard-remote || true
  fi

  if uv tool list | grep '^peard ' >/dev/null; then
    uv tool uninstall peard
  fi
}

case "$action" in
  INSTALL) install ;;
  UNINSTALL) uninstall ;;
esac
