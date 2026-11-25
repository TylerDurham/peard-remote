#!/usr/bin/env bash
# Install peard (editable, via uv tool), link the Noctalia plugin, and
# enable the systemd user service. Safe to re-run after pulling changes.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
plugins="${XDG_DATA_HOME:-$HOME/.local/share}/noctalia/plugins"
units="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"

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
