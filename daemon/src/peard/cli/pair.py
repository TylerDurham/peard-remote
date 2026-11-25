"""The `peard pair` command: pair with an Apple TV and save its credentials."""

import asyncio
from typing import List

from pyatv.const import Protocol
from pyatv.interface import BaseConfig
from rich.console import Console
from typer import Option
import typer

from peard.cli.ui import new_tv_table, select_from_table, spinner
from peard.core import pairing
from peard.core.discovery import scan

console = Console()


def command(timeout: int = Option(5, "--timeout", "-t")):
    """Pairs with an Apple TV on the local network."""

    # `tvs` is assigned inside the spinner block, so declare its type up front.
    tvs: List[BaseConfig]

    tbl = new_tv_table()

    with spinner("Scanning for TVs. Please wait..."):
        # Typer commands are synchronous, so run the async scan in its own event loop.
        tvs = asyncio.run(scan(timeout))

    if len(tvs) == 0:
        print("No Apple TVs found!")
        raise typer.Exit(code=1)

    # Number rows from 1, in the same order as `tvs`, so the choice maps back to a TV.
    count = 0
    for tv in tvs:
        count = count + 1
        tbl.add_row(f"{count}", tv.name, tv.identifier, f"{tv.address}")

    choice = select_from_table(tbl)

    # AirPlay is the only protocol we pair with for now.
    protocol = Protocol["AirPlay"]

    tv = tvs[int(choice) - 1]

    # `pairing.pair` calls one of these two, depending on which side provides the PIN.
    # It awaits `ask_pin`, so that one must be async.
    async def ask_pin() -> int:
        return int(typer.prompt("Enter the PIN shown on the TV"))

    def show_pin(pin: int) -> None:
        console.print(f"Enter this PIN on the device: [bold]{pin}[/bold]")

    # The scan's event loop is closed by now, so pairing runs in a new one. It looks the
    # TV up again by identifier and saves the credentials to the config.
    asyncio.run(
        pairing.pair(
            identifier=str(tv.identifier),
            protocol=protocol,
            ask_pin=ask_pin,
            show_pin=show_pin,
        )
    )
