
import asyncio
from typing import Optional

import pyatv
from pyatv.const import Protocol
import typer

from peard.cli.ui import spinner
from peard.core import discovery
from peard.core.config import Config


def cmd_key(identifier: Optional[str] = None):
    config = Config.load()

    if identifier == None:
        identifier = config.active

    creds = config.get_by_id(str(identifier))

    with spinner("Scanning for TVs. Please wait..."):
        tvs = asyncio.run(discovery.scan(5))

    if len(tvs) == 0:
        print("No Apple TVs found!")
        raise typer.Exit(code=1)

    tv = tvs[0]

    protocol = Protocol["AirPlay"]
    tv.set_credentials(protocol=protocol, credentials=creds.credentials)

    conn = asyncio.run(pyatv.connect(loop=asyncio.get_running_loop(), config=tv))
    

    
