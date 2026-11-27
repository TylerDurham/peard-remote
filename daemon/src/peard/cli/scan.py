"""The `peard scan` command: find Apple TVs on the local network."""

import asyncio
from typing import Annotated

from pyatv.interface import BaseConfig
from rich.console import Console
from typer import Option

from peard.cli.ui import new_tv_table, spinner
from peard.core.config import Config
from peard.core.discovery import scan

console = Console()


def command(
    hosts: Annotated[
        list[str] | None,
        Option(
            "--hosts",
            "-H",
            help="Ask this IP address directly instead of using mDNS. Repeat to ask several.",
        ),
    ] = None,
    identifier: Annotated[
        str | None,
        Option("--identifier", "-i", help="Only find the TV with this identifier."),
    ] = None,
    timeout: Annotated[
        int, Option("--timeout", "-t", help="How many seconds to scan for TVs.")
    ] = 5,
):
    """Scans the network for compatible Apple TV devices.

    \f
    Prints a table of the TVs found, with their protocols and whether they are paired.

    Args:
        hosts: Ask these IP addresses directly instead of using mDNS.
        identifier: Only find the TV with this unique identifier.
        timeout: How many seconds to scan for.
    """
    # `tvs` is assigned inside the spinner block, so declare its type up front.
    tvs: list[BaseConfig]
    tbl = new_tv_table()

    with spinner("Scanning for TVs. Please wait..."):
        # Typer commands are synchronous, so run the async scan in its own event loop.
        tvs = asyncio.run(scan(hosts=hosts, timeout=timeout, identifier=identifier))

    paired = {device.identifier for device in Config.load().devices}

    # Number rows from 1.
    count = 0
    for tv in tvs:
        count = count + 1
        protocols = sorted(service.protocol.name for service in tv.services)
        tbl.add_row(
            f"{count}",
            tv.name,
            tv.identifier,
            f"{tv.address}",
            ", ".join(protocols),
            # A TV has several identifiers, and any of them may be the saved one.
            str(not paired.isdisjoint(tv.all_identifiers)),
        )

    console.print(tbl)
