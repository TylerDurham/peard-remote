"""The `peard` command line, which puts the commands from the other modules together."""

from typer import Typer

from peard.cli import key, list, pair, scan, serve, set

app = Typer()

app.command(name="scan")(scan.command)
app.command(name="list")(list.command)
app.command(name="key")(key.command)
app.add_typer(set.app, name="set", help="Changes a setting.")
app.command(name="pair")(pair.command)
app.command(name="serve")(serve.command)

if __name__ == "__main__":
    app()
