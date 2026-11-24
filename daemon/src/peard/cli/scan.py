import asyncio
from typing import List, Optional

from pyatv.interface import BaseConfig
from rich.console import Console
from typer import Option
from peard.cli.ui import new_tv_table, spinner
from peard.core.discovery import scan

console = Console()


def cmd_scan(
    hosts: Optional[List[str]] = Option(
        None, "--hosts", "-H", help="One or more host ip addresses"
    ),
    identifier: Optional[str] = Option(
        None, "--identifier", "-i", help="The identifier."
    ),
    timeout: int = Option(5, "--timeout", "-t"),
):
    """Scans the network for compatible Apple TV devices."""

    tvs: List[BaseConfig]
    tbl = new_tv_table()

    with spinner("Scanning for TVs. Please wait..."):
        tvs = asyncio.run(scan(timeout))

    count = 0
    for tv in tvs:
        count = count + 1
        tbl.add_row(f"{count}", tv.name, tv.identifier, f"{tv.address}")

    console.print(tbl)
