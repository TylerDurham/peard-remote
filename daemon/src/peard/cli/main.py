from typer import Typer

from peard.cli.pair import pair
from peard.cli.scan import cmd_scan

app = Typer()

app.command(name="scan")(cmd_scan)
app.command()(pair)

if __name__ == "__main__":
    app()
