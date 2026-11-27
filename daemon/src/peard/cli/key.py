"""The `peard key` command: send a remote command to a paired Apple TV."""

import asyncio

import typer
from pyatv import exceptions

from peard.cli.ui import spinner
from peard.core.config import Config
from peard.core.controller import Controller


async def _command(identifier: str, command: str) -> None:
    """Connect to a TV, send it a single command and disconnect.

    Args:
        identifier: The unique identifier of the TV.
        command: The name of a method of pyatv's RemoteControl, such as `play_pause`.

    Raises:
        LookupError: If the TV couldn't be found on the network.
        PermissionError: If the TV hasn't been paired.
        AttributeError: If the command doesn't exist.
    """
    # A connection only works in the event loop that made it, so it has to be
    # used and closed in here.
    controller = Controller()
    try:
        atv = await controller.get(identifier)
        # Commands are the method names of pyatv's RemoteControl, such as `play_pause`.
        # They aren't checked first, so an unknown one raises an AttributeError.
        await getattr(atv.remote_control, command)()

    finally:
        await controller.close()


def command(command: str, identifier: str | None = None):
    """Sends a command to a paired Apple TV (the active one by default).

    \f
    Args:
        command: The name of a method of pyatv's RemoteControl, such as `play_pause`.
        identifier: The unique identifier of the TV. Defaults to the active TV.

    Raises:
        typer.Exit: With code 1 if there is no TV to send to, or it couldn't be
            reached.
    """
    if identifier is None:
        identifier = Config.load().active

    if identifier is None:
        print("No active Apple TV. Run `peard set active` first.")
        raise typer.Exit(code=1)

    try:
        with spinner("Connecting. Please wait..."):
            asyncio.run(_command(identifier, command))
    # Raised by the controller if the TV wasn't found, or isn't paired.
    except (LookupError, PermissionError) as e:
        print(e)
        raise typer.Exit(code=1)
    # Raised by pyatv if the TV was found, but connecting to it failed.
    except (exceptions.AuthenticationError, exceptions.ConnectionFailedError) as e:
        print(f"Could not connect to {identifier}: {e}")
        raise typer.Exit(code=1)

    print(f"Connected to {identifier}.")
