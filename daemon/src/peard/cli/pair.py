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

    tvs: List[BaseConfig]

    tbl = new_tv_table()

    with spinner("Scanning for TVs. Please wait..."):
        tvs = asyncio.run(scan(timeout))

    if len(tvs) == 0:
        print("No Apple TVs found!")
        raise typer.Exit(code=1)

    count = 0
    for tv in tvs:
        count = count + 1
        tbl.add_row(f"{count}", tv.name, tv.identifier, f"{tv.address}")

    choice = select_from_table(tbl)

    protocol = Protocol["AirPlay"]

    tv = tvs[int(choice) - 1]

    async def ask_pin() -> int:
        return int(typer.prompt("Enter the PIN shown on the TV"))

    def show_pin(pin: int) -> None:
        console.print(f"Enter this PIN on the device: [bold]{pin}[/bold]")

    asyncio.run(
        pairing.pair(
            identifier=str(tv.identifier),
            protocol=protocol,
            ask_pin=ask_pin,
            show_pin=show_pin,
        )
    )
