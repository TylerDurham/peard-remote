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


def select_from_table(tbl: Table) -> int:
    count = len(tbl.rows)

    console.print(tbl)

    while True:
        choice = typer.prompt(
            f"Enter the number of a TV to select (1-{count}, q to quit)"
        ).strip()
        if choice.lower() in ("q", "quit"):
            raise typer.Exit(code=1)
        if choice.isdecimal() and 1 <= int(choice) <= count:
            break
        print(f"Invalid choice {choice!r}: enter a number from 1 to {count}.")
    return int(choice)


@contextmanager
def spinner(
    description: str,
    *,
    console: Console = console,
    transient: bool = True,
    cb: Callable | None = None,
):
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
