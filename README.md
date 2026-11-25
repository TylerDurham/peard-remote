# peard-remote

<div align="center">
  <img src="media/peard-250x250.png" width="250" alt="peard logo"/>
</div>

*An Apple TV remote you pair with — so, a pear'd remote.*

An Apple TV remote for the [Noctalia](https://noctalia.dev) v5 bar, built on
[pyatv](https://pyatv.dev).

<div align="center">
  <img src="media/screenshot.png" width="800" alt="The remote panel open below the Noctalia bar"/>
</div>

## Features

- Start, Stop, Play, Pause Apple TVs
- Navigate, skip, change the volume, and wake or sleep your TV
- See what's playing, with artwork and progress, right from the bar
- Multiple Apple TV support
- CLI for securely pairing with your Apple TVs

Typing on the TV, launching apps and setting an exact volume aren't supported yet. The
plugin hides or disables those controls.

## How it works

`peard` is a small local daemon that connects to your Apple TVs. The Noctalia plugin
talks to it over HTTP on `127.0.0.1:7655`.

```
daemon/       peard: the CLI and the API server (Python)
plugin/       the Noctalia bar widget and panels (Luau)
install.sh    installs or uninstalls both, plus a systemd user service
```

## Install

You'll need Linux with systemd, [uv](https://docs.astral.sh/uv/) and Noctalia v5.

```sh
git clone https://github.com/TylerDurham/peard-remote.git
cd peard-remote
./install.sh
```

This copies the daemon and plugin, so they keep working if you move or delete the folder.
To update, pull the changes and re-run `install.sh`. To uninstall, run
`./install.sh --uninstall`, which keeps your paired TVs.

Then pair with a TV:

```sh
peard pair
```

The TV you paired last is the one you control. To switch between TVs, use the picker in
the remote or run `peard set active`.

Finally, add the widget to a bar in `~/.config/noctalia/config.toml`:

```toml
end = [ ..., "appletv", ... ]

[widget.appletv]
type = "dtd/peard-remote:remote"
```

## Usage

Click the widget to open the remote, right-click it to play or pause, and scroll on it to
change the volume. With the remote open, these keys work too:

| Key       | Action       |
| --------- | ------------ |
| Arrows    | Navigate     |
| Return    | Select       |
| Backspace | Back / Menu  |
| Space     | Play / Pause |
| H         | Home         |

You can also bind your own keys to these commands:

```sh
noctalia msg plugin dtd/peard-remote:bridge all key play_pause
noctalia msg plugin dtd/peard-remote:bridge all key-hold select
noctalia msg plugin dtd/peard-remote:bridge all power toggle
noctalia msg plugin dtd/peard-remote:bridge all device "Office"
```

### CLI

| Command            | Description                                  |
| ------------------ | -------------------------------------------- |
| `peard scan`       | Find Apple TVs on the network                |
| `peard pair`       | Pair with an Apple TV and make it active     |
| `peard list`       | List paired Apple TVs                        |
| `peard set active` | Choose the Apple TV to control               |
| `peard set port`   | Change the port the server listens on        |
| `peard key <name>` | Send a command, such as `up` or `play_pause` |
| `peard serve`      | Start the API server                         |

Run any command with `--help` to see its options.

### API

| Endpoint                | Description                                         |
| ----------------------- | --------------------------------------------------- |
| `GET /health`           | Check that the server is running                    |
| `GET /devices`          | List paired Apple TVs                               |
| `GET /events`           | Stream the active TV's state (server-sent events)   |
| `POST /device`          | Set the active TV, with `{"id": "Office"}`          |
| `POST /key/{name}`      | Send a key, with `?action=` `tap`, `double`, `hold` |
| `POST /power/{command}` | `on`, `off` or `toggle`                             |

`POST` requests need an `X-Pear` header, which keeps websites from controlling your TVs:

```sh
curl -X POST -H 'X-Pear: 1' localhost:7655/key/play_pause
```

## Configuration

Paired TVs, the active TV and the port are saved in `~/.config/peard-remote/config.json`.
The file holds your pairing credentials, so only your user can read it.

The daemon and the plugin share this file. To change the port, run
`peard set port <port>` and `systemctl --user restart peard.service`, and the plugin
follows. `peard serve --port` doesn't change the file, so the plugin won't follow it. To
point the plugin somewhere else, set its Bridge URL in Noctalia.

A `config.toml` from an older version is converted automatically and kept as
`config.toml.bak`. It holds your credentials too, and you can delete it.

## Troubleshooting

- **No TVs found:** make sure the TV is awake and on the same network, and that your
  firewall [allows mDNS](#allowing-mdns-through-a-firewall) (`5353/udp`). A longer scan can
  help (`peard scan --timeout 10`), as can asking a TV directly
  (`peard scan --hosts <tv-ip>`)
- **No TV selected** or **No active Apple TV:** choose a paired TV with the picker in the
  remote, or run `peard set active`
- **Not connected:** the daemon is running but can't reach the selected TV. The remote
  shows why; `journalctl --user -u peard.service` has more
- **Bridge not running:** check `systemctl --user status peard.service`

### Allowing mDNS through a firewall

These commands scan for Apple TVs, so they need mDNS to work:

```sh
peard scan
peard pair
peard list    # without mDNS, shows every TV as offline
```

The daemon and `peard key` scan for the TV too, to connect to it.

When you scan, Apple TVs reply straight to your computer, so rules that only allow the mDNS
multicast address (`224.0.0.251`), such as firewalld's `mdns` service, aren't enough. Use
the commands for the firewall you have:

**ufw** (Ubuntu, Mint, CachyOS)

```sh
sudo ufw allow 5353/udp comment 'mDNS'
```

Or, more securely, only allow your own network (change `192.168.1.0/24` to match yours):

```sh
sudo ufw allow from 192.168.1.0/24 to any port 5353 proto udp comment 'mDNS'
```

**firewalld** (Fedora, RHEL, openSUSE)

```sh
sudo firewall-cmd --permanent --add-port=5353/udp
sudo firewall-cmd --reload
```

**nftables**, if your table and chain are `inet filter` and `input` (see
`sudo nft list ruleset`)

```sh
sudo nft insert rule inet filter input udp dport 5353 accept
```

**iptables**

```sh
sudo iptables -I INPUT -p udp --dport 5353 -j ACCEPT
```

The `nft` and `iptables` rules are lost on reboot unless you save them, for example in
`/etc/nftables.conf` or with your distribution's iptables service.

## Development

Install with `./install.sh --dev-mode` to link to the daemon and plugin in this folder
instead of copying them. Keep the folder where it is, and run
`systemctl --user restart peard.service` after changing the daemon.

The [Justfile](daemon/Justfile) in `daemon/` has recipes for common tasks:

```sh
cd daemon
just sync           # install dependencies
just run serve      # run the CLI
just lint           # check for lint errors
just fmt            # format the code
```
