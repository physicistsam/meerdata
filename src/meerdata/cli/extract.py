"""`meerdata extract` command."""

from pathlib import Path

import click

from meerdata.cli import cli
from meerdata.cli.common import (
    _ensure_job_dirs,
    data_folder_option,
    dry_run_option,
    slurm_override_option,
    venv_option,
)
from meerdata.cli.console import console, header
from meerdata.cli.slurm import _run_data_jobs


@cli.command()
@click.option(
    "-r",
    "--rdb-file",
    required=True,
    type=click.Path(exists=True, resolve_path=True, path_type=Path),
    help="Path to local RDB file on disk.",
)
@click.option(
    "-c",
    "--correlation",
    type=click.Choice(["auto", "cross", "all"]),
    default="auto",
    show_default=True,
    help="Type of correlation data to extract: auto (autocorrelations), "
    "cross (OTF measurement set), all (both)",
)
@data_folder_option
@dry_run_option
@venv_option
@slurm_override_option
@click.pass_obj
def extract(
    site,
    rdb_file,
    correlation,
    data_folder,
    dry_run,
    venv,
    slurm_override,
):
    """Extract auto or cross-correlation from local data."""
    # Infer cbid from file path (assume .../<cbid>_sdp_l0.full.rdb)
    cbid = rdb_file.stem.split("_")[0]

    # Set up output directories
    dest = data_folder / cbid
    full_dest = rdb_file.parent
    ms_path = dest / f"{cbid}_sdp_l0.ms"

    # Create output directories
    _ensure_job_dirs()
    dest.mkdir(parents=True, exist_ok=True)

    header(f"Extracting {correlation} correlation data for CBID: {cbid}")
    console.print(f"  Source RDB: [cyan]{rdb_file}[/cyan]")
    console.print(f"  Destination: [cyan]{dest}[/cyan]")

    # Determine which steps to run based on correlation type (no download)
    steps = []
    if correlation in ["auto", "all"]:
        steps.append("auto")
    if correlation in ["cross", "all"]:
        steps.append("ms")
    steps.append("cleanup")  # Always cleanup at the end

    _run_data_jobs(
        steps,
        cbid,
        dest,
        full_dest,
        ms_path,
        rdb_file,
        site,
        venv_path=venv,
        dry_run=dry_run,
        slurm_override=slurm_override,
    )
