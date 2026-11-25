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
install.sh    installs both, plus a systemd user service
```

## Install

You'll need Linux with systemd, [uv](https://docs.astral.sh/uv/) and Noctalia v5.

```sh
git clone https://github.com/TylerDurham/peard-remote.git
cd peard-remote
./install.sh
```

The daemon and plugin are linked to this folder, so keep it around. Re-run `install.sh`
after pulling changes.

Then pair with a TV, and choose which one to control:

```sh
peard pair
peard set-active
```

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
| `peard pair`       | Pair with an Apple TV                        |
| `peard list`       | List paired Apple TVs                        |
| `peard set-active` | Choose the Apple TV to control               |
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

Paired TVs, the active TV and the port are saved in `~/.config/peard-remote/config.toml`.
The file holds your pairing credentials, so only your user can read it.

If you change the port, change the plugin's `endpoint` setting in Noctalia to match.

## Troubleshooting

- **No TVs found:** make sure the TV is awake and on the same network, and that your
  firewall allows mDNS (`5353/udp`). A longer scan can help (`peard scan --timeout 10`), as
  can asking a TV directly (`peard scan --hosts <tv-ip>`)
- **Bridge not running:** check `systemctl --user status peard.service`

## Development

The [Justfile](daemon/Justfile) in `daemon/` has recipes for common tasks:

```sh
cd daemon
just sync           # install dependencies
just run serve      # run the CLI
just lint           # check for lint errors
just fmt            # format the code
```
