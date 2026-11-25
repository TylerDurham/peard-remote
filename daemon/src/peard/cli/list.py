import asyncio

from rich.console import Console
from typer import Option

from peard.cli.ui import new_tv_table
from peard.core import discovery
from peard.core.config import Config

console = Console()


def cmd_list(
    json: bool = Option(False, "--json", "-j", help="Format the output as JSON.")
):
    """Lists all paired Apple TVs."""
    cfg = Config.load()
    tbl = new_tv_table()
    tbl.add_column("Active")

    if json:
        console.print_json(data=cfg)

    for device in cfg.devices:
        tvs = asyncio.run(discovery.scan(timeout=1, identifier=device.identifier))
        active = device.identifier == cfg.active
        tv = tvs[0]
        tbl.add_row(
            "1",
            device.name,
            device.identifier,
            str(tv.address),
            device.protocol,
            str(True),
            str(active),
        )


    console.print(f"Active TV is '{cfg.active}'")
    console.print(tbl)
