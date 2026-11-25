import asyncio
from typing import Optional

from rich.console import Console
import typer

from peard.cli.ui import new_tv_table, spinner
from peard.core import discovery
from peard.core.config import Config

console = Console()


def cmd_set_active(identifier: Optional[str] = None):
    """Sets the active Apple TV."""
    config = Config.load()

    if not config.devices:
        console.print("No paired Apple TVs.")
        raise typer.Exit(code=1)

    if identifier is None:
        with spinner("Looking for paired TVs. Please wait..."):
            tvs = asyncio.run(discovery.scan(timeout=2))

        addresses = {
            tv_id: str(tv.address) for tv in tvs for tv_id in tv.all_identifiers
        }

        tbl = new_tv_table()
        tbl.add_column("Active")

        for number, device in enumerate(config.devices, start=1):
            tbl.add_row(
                str(number),
                device.name,
                device.identifier,
                addresses.get(device.identifier, "offline"),
                device.protocol,
                str(True),
                str(device.identifier == config.active),
            )

        console.print(tbl)

        count = len(config.devices)
        while True:
            choice = typer.prompt(
                f"Enter the number of the TV to make active (1-{count}, q to quit)"
            ).strip()
            if choice.lower() in ("q", "quit"):
                raise typer.Exit(code=1)
            if choice.isdecimal() and 1 <= int(choice) <= count:
                break
            print(f"Invalid choice {choice!r}: enter a number from 1 to {count}.")

        # Index the saved devices shown in the table, not the scan results.
        device = config.devices[int(choice) - 1]
    else:
        try:
            device = config.get_by_id(identifier)
        except KeyError:
            print(f"No paired Apple TV with identifier {identifier!r}.")
            raise typer.Exit(code=1)

    config.active = device.identifier
    config.save()
    print(f"Active TV is now {device.name} ({device.identifier}).")
