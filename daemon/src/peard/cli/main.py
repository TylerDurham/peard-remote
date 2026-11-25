from typer import Typer

from peard.cli import scan, key, list, set_active, pair, serve

app = Typer()

app.command(name="scan")(scan.command)
app.command(name="list")(list.command)
app.command(name="key")(key.command)
app.command(name="set-active")(set_active.command)
app.command(name="pair")(pair.command)
app.command(name="serve")(serve.command)

if __name__ == "__main__":
    app()
