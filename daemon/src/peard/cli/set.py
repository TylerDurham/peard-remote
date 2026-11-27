"""The `peard set` commands: change the settings saved in the config."""

import asyncio

import typer
from rich.console import Console
from typer import Argument, Typer

from peard.cli.ui import new_tv_table, select_from_table, spinner
from peard.core import discovery
from peard.core.config import Config

console = Console()

# Each setting is a command of its own, such as `peard set port`.
app = Typer(no_args_is_help=True)


@app.command()
def active(
    identifier: str | None = Argument(
        None, help="The identifier of a paired TV. Choose from a list if omitted."
    ),
):
    """Sets the active Apple TV.

    \f
    Args:
        identifier: The unique identifier of a paired TV. Without one, the user chooses
            from a table of the paired TVs.

    Raises:
        typer.Exit: With code 1 if no TVs are paired, the identifier doesn't match one,
            or the user quit.
    """
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


@app.command()
def port(
    port: int = Argument(min=1, max=65535, help="The port for the server to use."),
):
    """Sets the port that the server listens on.

    \f
    A running server only picks up the new port when it restarts.

    Args:
        port: The port, from 1 to 65535.
    """
    config = Config.load()
    config.port = port
    config.save()

    # Unlike the active TV, a running server only reads the port when it starts.
    print(f"Port is now {port}. To use it, restart the server:")
    print("  systemctl --user restart peard.service")
