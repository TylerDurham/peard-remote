import asyncio
from typing import Optional

from pyatv import exceptions
import typer

from peard.cli.ui import spinner
from peard.core.config import Config
from peard.core.controller import Controller


async def _connect(identifier: str, command: str) -> None:
    # A connection only works in the event loop that made it, so it has to be
    # used and closed in here.
    controller = Controller()
    try:
        atv = await controller.get(identifier)
        await getattr(atv.remote_control, command)()

    finally:
        await controller.close()


def command(command: str, identifier: Optional[str] = None):
    """Connects to a paired Apple TV (the active one by default)."""
    if identifier is None:
        identifier = Config.load().active

    if identifier is None:
        print("No active Apple TV. Run `peard set-active` first.")
        raise typer.Exit(code=1)

    try:
        with spinner("Connecting. Please wait..."):
            asyncio.run(_connect(identifier, command))
    except (LookupError, PermissionError) as e:
        print(e)
        raise typer.Exit(code=1)
    except (exceptions.AuthenticationError, exceptions.ConnectionFailedError) as e:
        print(f"Could not connect to {identifier}: {e}")
        raise typer.Exit(code=1)

    print(f"Connected to {identifier}.")
