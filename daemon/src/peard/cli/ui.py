"""Tables, prompts and spinners shared by the CLI commands."""

from collections.abc import Callable
from contextlib import contextmanager

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

console = Console()


def new_tv_table() -> Table:
    """Create an empty table with the columns used to list TVs.

    Returns:
        A table with #, Name, Identifier, Address, Protocols and Paired columns.
    """
    tbl = Table()
    tbl.add_column("#")
    tbl.add_column("Name")
    tbl.add_column("Identifier")
    tbl.add_column("Address")
    tbl.add_column("Protocols")
    tbl.add_column("Paired")
    return tbl


def select_from_table(tbl: Table) -> int:
    """Print a table and ask the user to choose a row by number, until they enter a
    valid one.

    Args:
        tbl: The table, with rows numbered from 1.

    Returns:
        The number of the row the user chose, from 1.

    Raises:
        typer.Exit: With code 1 if the user quit.
    """
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
    """Show a spinner with a message while the block runs.

    Args:
        description: The message to show next to the spinner.
        console: The console to show the spinner on.
        transient: Remove the spinner when the block ends.
        cb: Called once, after the spinner has started.

    Yields:
        A function that changes the message.
    """
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
