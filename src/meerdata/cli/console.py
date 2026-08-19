"""Rich-formatted logging for user-facing CLI status messages.

Kept separate from the raw content dumped for `--dry-run` (sbatch scripts,
local command bodies): those are printed verbatim via plain `click.echo` so
their exact text stays byte-for-byte reproducible.
"""

import logging

from rich.console import Console
from rich.highlighter import NullHighlighter
from rich.logging import RichHandler

console = Console(soft_wrap=True, highlight=False)

_handler = RichHandler(
    console=console,
    show_time=False,
    show_path=False,
    markup=True,
    highlighter=NullHighlighter(),
)
logging.basicConfig(level=logging.INFO, format="%(message)s", handlers=[_handler])

logger = logging.getLogger("meerdata")


def header(message: str) -> None:
    logger.info(f"[bold cyan]{message}[/bold cyan]")


def success(message: str) -> None:
    logger.info(f"[green]✓[/green] {message}")


def warning(message: str) -> None:
    logger.warning(message)


def failure(message: str) -> None:
    logger.error(message)
