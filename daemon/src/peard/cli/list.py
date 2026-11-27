"""The `peard list` command: show the paired Apple TVs saved in the config."""

import asyncio
from dataclasses import asdict

from rich.console import Console
from typer import Option

from peard.cli.ui import new_tv_table, spinner
from peard.core import discovery
from peard.core.config import Config

console = Console()


def command(
    json: bool = Option(False, "--json", "-j", help="Format the output as JSON."),
    timeout: int = Option(5, "--timeout", "-t"),
):
    """Lists all paired Apple TVs.

    \f
    Scans the network to show each TV's address, unless printing JSON.

    Args:
        json: Print the saved config as JSON, without the credentials.
        timeout: How many seconds to scan for.
    """
    cfg = Config.load()

    # JSON output is just the saved config, so it doesn't need a scan.
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
        # Typer commands are synchronous, so run the async scan in its own event loop.
        # One scan covers every TV, which is faster than scanning for each in turn.
        tvs = asyncio.run(discovery.scan(timeout=timeout))

    # Addresses aren't saved in the config, so take them from the scan. A TV has several
    # identifiers, and any of them may be the saved one.
    addresses = {
        identifier: str(tv.address) for tv in tvs for identifier in tv.all_identifiers
    }

    tbl = new_tv_table()
    tbl.add_column("Active")

    # List every saved TV, including those the scan didn't find.
    for number, device in enumerate(cfg.devices, start=1):
        tbl.add_row(
            str(number),
            device.name,
            device.identifier,
            # "offline" only means no reply to this scan; the TV may still be on.
            addresses.get(device.identifier, "offline"),
            device.protocol,
            str(True),  # Only paired TVs are saved in the config.
            str(device.identifier == cfg.active),
        )

    console.print(f"Active TV is '{cfg.active}'")
    console.print(tbl)
