
from contextlib import contextmanager
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.console import Console
import typer
from rich.table import Table
from pyatv.interface import BaseConfig
from typing import Callable, List

console = Console()

def new_tv_table() -> Table:
    tbl = Table()
    tbl.add_column("#")
    tbl.add_column("Name")
    tbl.add_column("Identifier")
    tbl.add_column("Address")
    tbl.add_column("Protocols")
    tbl.add_column("Paired")
    return tbl

@contextmanager
def spinner(description: str, *, console: Console = console, transient: bool = True, cb: Callable | None = None):
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=transient,
    ) as progress:
        task = progress.add_task(description=description, total=None)

        def update(text: str) -> None:
            progress.update(task, description=text)

        if cb is not None:
            cb()

        yield update
