"""The `peard set-active` command: choose which paired Apple TV to control."""

import asyncio
from typing import Optional

from rich.console import Console
import typer

from peard.cli.ui import new_tv_table, select_from_table, spinner
from peard.core import discovery
from peard.core.config import Config

console = Console()


def command(identifier: Optional[str] = None):
    """Sets the active Apple TV."""
    config = Config.load()

    if not config.devices:
        console.print("No paired Apple TVs.")
        raise typer.Exit(code=1)

    # Without an identifier, let the user choose from a table.
    if identifier is None:
        with spinner("Looking for paired TVs. Please wait..."):
            # Only used to show addresses, so a short scan is enough. Typer commands are
            # synchronous, so run it in its own event loop.
            tvs = asyncio.run(discovery.scan(timeout=2))

        # A TV has several identifiers, and any of them may be the saved one.
        addresses = {
            tv_id: str(tv.address) for tv in tvs for tv_id in tv.all_identifiers
        }

        tbl = new_tv_table()
        tbl.add_column("Active")

        # List every saved TV, so that one that is offline can be chosen too.
        for number, device in enumerate(config.devices, start=1):
            tbl.add_row(
                str(number),
                device.name,
                device.identifier,
                addresses.get(device.identifier, "offline"),
                device.protocol,
                str(True),  # Only paired TVs are saved in the config.
                str(device.identifier == config.active),
            )

        choice = select_from_table(tbl)

        # Index the saved devices shown in the table, not the scan results.
        device = config.devices[int(choice) - 1]
    else:
        try:
            device = config.get_by_id(identifier)
        except KeyError:
            print(f"No paired Apple TV with identifier {identifier!r}.")
            raise typer.Exit(code=1)

    # A running server notices the change by itself and switches to this TV.
    config.active = device.identifier
    config.save()
    print(f"Active TV is now {device.name} ({device.identifier}).")
