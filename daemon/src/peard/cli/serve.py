"""The `peard serve` command: run the HTTP API for the Noctalia plugin."""

from typing import Annotated

import typer
from typer import Option

from peard.core.config import Config


def command(
    port: Annotated[
        int | None,
        Option(
            "--port",
            "-p",
            min=1,
            max=65535,
            help="The port to listen on. Defaults to the port in the config.",
        ),
    ] = None,
):
    """Starts the local API server.

    \f
    Only listens on 127.0.0.1, and runs until it is stopped.

    Args:
        port: The port to listen on. Defaults to the port in the config.

    Raises:
        typer.Exit: With code 1 if the server couldn't start, for example because the
            port is in use.
    """
    # Imported here so that the other commands don't have to load the web framework.
    import uvicorn

    from peard.api.server import app

    if port is None:
        port = Config.load().port

    class Server(uvicorn.Server):
        """A uvicorn server that ends the event streams when it shuts down."""

        async def shutdown(self, sockets=None) -> None:
            """Close the monitor, then shut down as usual.

            Args:
                sockets: The sockets to close, passed on to uvicorn.
            """
            # End the event streams, which would otherwise keep the server running.
            app.state.monitor.close()
            await super().shutdown(sockets)

    # The API can control your TVs, so only listen on this computer.
    server = Server(
        uvicorn.Config(app, host="127.0.0.1", port=port, timeout_graceful_shutdown=5)
    )
    try:
        server.run()
    except KeyboardInterrupt:
        pass

    if not server.started:
        raise typer.Exit(code=1)
