"""The `peard serve` command: run the HTTP API for the Noctalia plugin."""

from typing import Optional

import typer
from typer import Option

from peard.core.config import Config


def command(
    port: Optional[int] = Option(
        None,
        "--port",
        "-p",
        min=1,
        max=65535,
        help="The port to listen on. Defaults to the port in the config.",
    ),
):
    """Starts the local API server."""

    # Imported here so that the other commands don't have to load the web framework.
    import uvicorn

    from peard.api.server import app

    if port is None:
        port = Config.load().port

    class Server(uvicorn.Server):
        async def shutdown(self, sockets=None) -> None:
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
