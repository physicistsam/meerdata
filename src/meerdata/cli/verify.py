"""`meerdata verify` command."""

import subprocess
from math import prod

import click
import katdal
from rich.table import Table

from meerdata.cli import cli
from meerdata.cli.common import data_folder_option
from meerdata.cli.console import console, failure, header, warning


def _check_disk_usage(block_dir):
    """Return total disk usage of `block_dir` in GB, or "ERR" on failure."""
    try:
        du_proc = subprocess.run(
            ["du", "-sBG", str(block_dir)],
            capture_output=True,
            text=True,
            check=True,
        )
        du_out = du_proc.stdout.strip().split()[0]
        # Remove trailing 'G' and convert to int
        return int(du_out.rstrip("G"))
    except (subprocess.CalledProcessError, OSError, ValueError, IndexError) as e:
        failure(f"Error getting disk usage for {block_dir}: {e}")
        return "ERR"


def _check_chunk_completeness(rdb_path, block_dir):
    """Return the number of missing chunk files, or None if the RDB could
    not be opened with katdal.
    """
    try:
        dataset = katdal.open(str(rdb_path))
    except Exception as e:
        failure(f"Failed to open {rdb_path} with katdal: {e}")
        return None

    missing_chunks = 0
    for data_type, info in dataset.source.data.chunk_info.items():
        expected = prod(len(axis_chunks) for axis_chunks in info["chunks"])
        chunk_dir = block_dir / info["prefix"] / data_type
        actual = len(list(chunk_dir.glob("**/*.npy"))) if chunk_dir.exists() else 0
        if actual != expected:
            missing_chunks += expected - actual
            warning(f"{chunk_dir}: expected {expected} chunks, found {actual}")
    return missing_chunks


def _verify_block(block_dir, bn):
    """Verify a single data block and return its summary row."""
    rdb_path = block_dir / bn / f"{bn}_sdp_l0.full.rdb"
    if not block_dir.exists():
        failure(f"{block_dir} does not exist.")
        return {
            "bn": bn,
            "rdb_exists": False,
            "missing_chunks": None,
            "size_gb": 0,
        }

    size_gb = _check_disk_usage(block_dir)
    if size_gb == 0:
        warning(f"{block_dir} exists but is empty (disk usage: 0 GB)")

    if not rdb_path.exists():
        failure(f"{rdb_path} does not exist.")
        return {
            "bn": bn,
            "rdb_exists": False,
            "missing_chunks": None,
            "size_gb": size_gb,
        }

    console.print(f"  [green]✓[/green] {rdb_path} exists")
    missing_chunks = _check_chunk_completeness(rdb_path, block_dir)
    if missing_chunks == 0:
        console.print(f"  [green]✓[/green] {block_dir} data is complete")

    return {
        "bn": bn,
        "rdb_exists": True,
        "missing_chunks": missing_chunks,
        "size_gb": size_gb,
    }


def _discover_block_numbers(data_folder):
    """Return sorted block numbers found as immediate subdirectories of
    `data_folder` (any directory name made up entirely of digits).
    """
    return sorted(
        p.name for p in data_folder.iterdir() if p.is_dir() and p.name.isdigit()
    )


@cli.command()
@click.option(
    "-b",
    "--block-number",
    multiple=True,
    type=str,
    help="Block number(s) to verify. Can be specified multiple times.",
)
@click.option(
    "-a",
    "--all",
    "all_blocks",
    is_flag=True,
    help="Verify every block found directly under --data-folder, instead of "
    "specifying block numbers individually.",
)
@data_folder_option
def verify(block_number, all_blocks, data_folder):
    """Verify existence and completeness of data blocks."""
    if all_blocks:
        if block_number:
            warning("--all was given; ignoring explicit --block-number values.")
        block_number = _discover_block_numbers(data_folder)
        if not block_number:
            raise click.ClickException(f"No block directories found in {data_folder}.")
    elif not block_number:
        raise click.ClickException(
            "Specify at least one -b/--block-number, or use -a/--all."
        )

    header(f"Verifying {len(block_number)} block(s) in {data_folder}")
    summary = [_verify_block(data_folder / bn, bn) for bn in block_number]
    # Group failing blocks together, ahead of fully-verified ones.
    summary.sort(key=lambda row: row["rdb_exists"] and row["missing_chunks"] == 0)

    table = Table(title="Summary Report")
    table.add_column("Block Number")
    table.add_column("RDB Exists")
    table.add_column("Data Complete")
    table.add_column("Missing Chunks", justify="right")
    table.add_column("Disk Usage (GB)", justify="right")
    for row in summary:
        rdb_cell = "[green]YES[/green]" if row["rdb_exists"] else "[red]NO[/red]"
        if not row["rdb_exists"]:
            complete_cell, missing_cell = "-", "-"
        elif row["missing_chunks"] is None:
            complete_cell, missing_cell = "[red]ERROR[/red]", "-"
        else:
            complete_cell = (
                "[green]YES[/green]" if row["missing_chunks"] == 0 else "[red]NO[/red]"
            )
            missing_cell = str(row["missing_chunks"])
        table.add_row(
            row["bn"], rdb_cell, complete_cell, missing_cell, str(row["size_gb"])
        )
    console.print(table)
