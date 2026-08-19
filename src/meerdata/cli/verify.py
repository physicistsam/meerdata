"""`meerdata verify` command."""

import subprocess

import click
from rich.table import Table

from meerdata.cli import cli
from meerdata.cli.common import data_folder_option
from meerdata.cli.console import console, failure, header, warning


@cli.command()
@click.option(
    "-b",
    "--block-number",
    required=True,
    multiple=True,
    type=str,
    help="Block number(s) to verify. Can be specified multiple times.",
)
@data_folder_option
def verify(block_number, data_folder):
    """Verify existent and disk usage of data blocks."""
    header(f"Verifying {len(block_number)} block(s) in {data_folder}")
    summary = []
    for bn in block_number:
        block_dir = data_folder / bn
        if block_dir.exists() and block_dir.is_dir():
            # Get disk usage in GB
            try:
                du_proc = subprocess.run(
                    ["du", "-sBG", str(block_dir)],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                du_out = du_proc.stdout.strip().split()[0]
                # Remove trailing 'G' and convert to int
                size_gb = int(du_out.rstrip("G"))
            except (
                subprocess.CalledProcessError,
                OSError,
                ValueError,
                IndexError,
            ) as e:
                size_gb = "ERR"
                failure(f"Error getting disk usage for {block_dir}: {e}")
            if size_gb == 0:
                warning(f"{block_dir} exists but is empty (disk usage: 0 GB)")
            else:
                console.print(
                    f"  [green]✓[/green] {block_dir} exists, disk usage: {size_gb} GB"
                )
            summary.append((bn, True, size_gb))
        else:
            failure(f"{block_dir} does not exist.")
            summary.append((bn, False, 0))

    table = Table(title="Summary Report")
    table.add_column("Block Number")
    table.add_column("Exists")
    table.add_column("Disk Usage (GB)", justify="right")
    for bn, exists, size_gb in summary:
        exists_cell = "[green]YES[/green]" if exists else "[red]NO[/red]"
        table.add_row(bn, exists_cell, str(size_gb))
    console.print(table)
