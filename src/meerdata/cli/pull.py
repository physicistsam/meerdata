"""`meerdata pull` command."""

import click

from meerdata.cli import cli
from meerdata.cli.common import (
    _ensure_job_dirs,
    _extract_cbid_and_token_from_rdb_link,
    data_folder_option,
    dry_run_option,
    full_tmp_folder_option,
    rdb_link_option,
    slurm_override_option,
    venv_option,
)
from meerdata.cli.console import console, header
from meerdata.cli.slurm import _run_data_jobs


@cli.command()
@rdb_link_option
@click.option(
    "-c",
    "--correlation",
    type=click.Choice(["auto", "cross", "all"]),
    default="auto",
    show_default=True,
    help="Type of correlation data to pull: auto (autocorrelations), "
    "cross (OTF measurement set), all (both)",
)
@data_folder_option
@dry_run_option
@venv_option
@full_tmp_folder_option
@click.option(
    "--no-cleanup",
    is_flag=True,
    help="Skip the full raw data cleanup step at the end",
)
@slurm_override_option
@click.pass_obj
def pull(
    site,
    rdb_link,
    correlation,
    data_folder,
    dry_run,
    venv,
    full_tmp_folder,
    no_cleanup,
    slurm_override,
):
    """Download a data block."""
    cbid, _token = _extract_cbid_and_token_from_rdb_link(rdb_link)

    # Set up directories. Each download is saved to dest/<cbid> with 3 subdirectories
    # inside: <cbid>, <cbid>-sdp-l0, and <cbid>-sdp-l1-flags. The local RDB file lives
    # in the first subdirectory. MS file lives inside the main directory.
    dest = data_folder / cbid
    # Compute full_tmp_dest: use provided folder or default to data_folder/full_tmp/cbid
    full_tmp_dest = (
        full_tmp_folder if full_tmp_folder else data_folder / "full_tmp" / cbid
    )
    ms_path = dest / f"{cbid}_sdp_l0.ms"
    local_rdb = full_tmp_dest / cbid / f"{cbid}_sdp_l0.full.rdb"

    # Create/check that directories exist
    _ensure_job_dirs()
    dest.mkdir(parents=True, exist_ok=True)
    full_tmp_dest.mkdir(parents=True, exist_ok=True)

    header(f"Pulling {correlation} correlation data for CBID: {cbid}")
    console.print(f"  Destination: [cyan]{dest}[/cyan]")

    # Determine which steps to run based on correlation type
    steps = ["download"]  # Always download for pull command
    if correlation in ["auto", "all"]:
        steps.append("auto")
    if correlation in ["cross", "all"]:
        steps.append("ms")
    if not no_cleanup:
        steps.append("cleanup")  # Cleanup at the end unless --no-cleanup is specified

    _run_data_jobs(
        steps,
        cbid,
        dest,
        full_tmp_dest,
        ms_path,
        local_rdb,
        site,
        rdb_link=rdb_link,
        venv_path=venv,
        dry_run=dry_run,
        slurm_override=slurm_override,
    )
