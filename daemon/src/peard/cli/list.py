import asyncio
from dataclasses import asdict

from rich.console import Console
from typer import Option

from peard.cli.ui import new_tv_table, spinner
from peard.core import discovery
from peard.core.config import Config

console = Console()


def cmd_list(
    json: bool = Option(False, "--json", "-j", help="Format the output as JSON."),
    timeout: int = Option(5, "--timeout", "-t"),
):
    """Lists all paired Apple TVs."""
    cfg = Config.load()

    if json:
        data = asdict(cfg)
        for device in data["devices"]:
            # Never print pairing secrets.
            del device["credentials"]
        console.print_json(data=data)
        return

    if not cfg.devices:
        console.print("No paired Apple TVs.")
        return

    with spinner("Looking for paired TVs. Please wait..."):
        tvs = asyncio.run(discovery.scan(timeout=timeout))

    addresses = {
        identifier: str(tv.address) for tv in tvs for identifier in tv.all_identifiers
    }

    tbl = new_tv_table()
    tbl.add_column("Active")

    for number, device in enumerate(cfg.devices, start=1):
        tbl.add_row(
            str(number),
            device.name,
            device.identifier,
            addresses.get(device.identifier, "offline"),
            device.protocol,
            str(True),
            str(device.identifier == cfg.active),
        )

    console.print(f"Active TV is '{cfg.active}'")
    console.print(tbl)
