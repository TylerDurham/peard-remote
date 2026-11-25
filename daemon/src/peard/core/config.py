from pathlib import Path
from dataclasses import dataclass, field
from typing import List
import os
import tomllib

DEFAULT_DIR_NAME = "peard-remote"
DEFAULT_PORT = 8000


def config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / DEFAULT_DIR_NAME


def cache_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / DEFAULT_DIR_NAME


def config_path() -> Path:
    return config_dir() / "config.toml"


def _q(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


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
        path = config_path()
        if not path.exists():
            return cls()

        data = tomllib.loads(path.read_text())
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

    def save(self):

        path = config_path()
        path.parent.mkdir(parents=True, exist_ok=True)

        lines = [f"port = {self.port}"]
        if self.active:
            lines.append(f"active = {_q(self.active)}")

        for d in self.devices:
            lines += ["", "[[devices]]", f"identifier = {_q(d.identifier)}"]
            if d.name:
                lines.append(f"name = {_q(d.name)}")
            if d.credentials:
                lines.append(f"credentials = {_q(d.credentials)}")
            if d.description:
                lines.append(f"description = {_q(d.description)}")
            if d.protocol:
                lines.append(f"protocol = {_q(d.protocol)}")

        # The file holds pairing credentials, so keep it private to the user.
        path.touch(mode=0o600)
        path.chmod(0o600)
        path.write_text("\n".join(lines) + "\n")
        return path
