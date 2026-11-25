from typer import Typer

from peard.cli.key import cmd_key
from peard.cli.list import cmd_list
from peard.cli.pair import pair
from peard.cli.scan import cmd_scan
from peard.cli.set_active import cmd_set_active

app = Typer()

app.command(name="scan")(cmd_scan)
app.command(name="list")(cmd_list)
app.command(name="key")(cmd_key)
app.command(name="set-active")(cmd_set_active)
app.command()(pair)

if __name__ == "__main__":
    app()
