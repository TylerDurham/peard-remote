from pathlib import Path
from dataclasses import asdict, dataclass, field
from typing import Any, List
import json
import os
import tomllib

DEFAULT_DIR_NAME = "peard-remote"
DEFAULT_PORT = 7655


def config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / DEFAULT_DIR_NAME


def cache_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / DEFAULT_DIR_NAME


# The Noctalia plugin reads the port from this file too.
def config_path() -> Path:
    return config_dir() / "config.json"


@dataclass()
class Device:
    credentials: str
    name: str
    description: str
    identifier: str
    protocol: str


@dataclass()
class Config:
    active: str | None = None
    port: int = DEFAULT_PORT
    devices: List[Device] = field(default_factory=list)

    @classmethod
    def load(cls):
        cls._migrate_toml()

        path = config_path()
        if not path.exists():
            return cls()

        return cls._from_dict(json.loads(path.read_text(encoding="utf-8")))

    @classmethod
    def _migrate_toml(cls):
        """Convert the config.toml that older versions saved."""
        old = config_dir() / "config.toml"
        if config_path().exists() or not old.exists():
            return

        # The server and the CLI may both get here, and one of them will be first.
        try:
            data = tomllib.loads(old.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return

        cls._from_dict(data).save()
        try:
            old.rename(old.with_name("config.toml.bak"))
        except FileNotFoundError:
            pass

    @classmethod
    def _from_dict(cls, data: dict[str, Any]):
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
        for device in self.devices:
            if device.identifier == identifier:
                return device

        raise KeyError(f"Could not find a device with id '{identifier}'")

    def save(self):

        path = config_path()
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
