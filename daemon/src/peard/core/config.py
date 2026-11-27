import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_DIR_NAME = "peard-remote"
DEFAULT_PORT = 7655


def config_dir() -> Path:
    """Get the path to the config directory. Attempts to read from `XDG_CONFIG_HOME` and falls back
    to `$HOME/.config`.

    Returns:
        The Path to the config directory.
    """
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / DEFAULT_DIR_NAME


def cache_dir() -> Path:
    """Get the path to the cache directory. Attempts to read from `XDG_cache_HOME` and falls back
    to `$HOME/.cache`.

    Returns:
        The Path to the config directory.
    """
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / DEFAULT_DIR_NAME


# The Noctalia plugin reads the port from this file too.
def config_file() -> Path:
    """Gets the absolute path to the config file.

    Returns:
        The Path to the config file.

    """
    return config_dir() / "config.json"


@dataclass()
class Device:
    """A TV that has been paired and saved to the config file.

    Attributes:
        credentials: The pairing credentials pyatv returned, used to connect without
            pairing again. Keep these private.
        name: The TV's display name, such as "Living Room".
        description: The TV's model, such as "Apple TV 4K".
        identifier: The unique identifier pyatv uses for the TV.
        protocol: The name of the protocol the credentials belong to, such as "AirPlay".
    """

    credentials: str
    name: str
    description: str
    identifier: str
    protocol: str


@dataclass()
class Config:
    """The settings shared by the daemon, the CLI and the Noctalia plugin, saved as JSON
    in the file from `config_file()`.

    Attributes:
        active: The identifier of the TV that commands go to, or None if no TV is active.
        port: The port the daemon's HTTP server listens on.
        devices: The TVs that have been paired.
    """

    active: str | None = None
    port: int = DEFAULT_PORT
    devices: list[Device] = field(default_factory=list)

    @classmethod
    def load(cls):
        """Load the config from the file at `config_file()`.

        Returns:
            The saved Config, or a Config with default values if the file doesn't exist.
        """
        path = config_file()
        if not path.exists():
            return cls()

        return cls._from_dict(json.loads(path.read_text(encoding="utf-8")))

    @classmethod
    def _from_dict(cls, data: dict[str, Any]):
        """Build a Config from the dictionary read from the config file. Devices without
        an identifier are skipped, and missing values fall back to their defaults.

        Args:
            data: The parsed contents of the config file.

        Returns:
            The Config the dictionary describes.
        """
        active = data.get("active")

        devices = [
            Device(
                name=str(d.get("name", "")),
                identifier=str(d["identifier"]),
                description=str(d.get("description", "")),
                protocol=str(d.get("protocol", "")),
                credentials=str(d.get("credentials", "")),
            )
            for d in data.get("devices", [])
            if d.get("identifier")
        ]

        return cls(
            devices=devices, active=active, port=int(data.get("port", DEFAULT_PORT))
        )

    def get_by_id(self, identifier: str):
        """Gets the device from the config file using the specified `identifier`.

        Args:
            identifier: The unique identifier of the device.

        Returns:
            The device with the matching `identifier`.

        Raises:
            KeyError: If no device was found.
        """
        for device in self.devices:
            if device.identifier == identifier:
                return device

        raise KeyError(f"Could not find a device with id '{identifier}'")

    def save(self):
        """Save the config to the file at `config_file()`, creating its directory if
        needed. The file is replaced in one step, so readers never see a half-written
        file, and only the current user can read it.

        Returns:
            The Path the config was saved to.
        """
        path = config_file()
        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "port": self.port,
            "active": self.active,
            "devices": [asdict(d) for d in self.devices],
        }

        # Write a new file and swap it in, so that the server and the CLI never read a
        # half-written config from each other. Resolve first to keep symlinks working.
        target = path.resolve()
        tmp = target.with_name(f"{target.name}.{os.getpid()}.tmp")

        # The file holds pairing credentials, so keep it private to the user.
        tmp.touch(mode=0o600)
        tmp.chmod(0o600)
        text = json.dumps(data, indent=2, ensure_ascii=False)
        tmp.write_text(text + "\n", encoding="utf-8")
        tmp.replace(target)
        return path
