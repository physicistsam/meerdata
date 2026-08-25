"""`meerdata check` command."""

import click

from meerdata.cli import cli
from meerdata.cli.common import (
    _ensure_job_dirs,
    _extract_cbid_and_token_from_rdb_link,
    dry_run_option,
    rdb_link_option,
    sanity_check_folder_option,
    slurm_override_option,
    venv_option,
)
from meerdata.cli.console import console, header
from meerdata.cli.slurm import _run_data_jobs


@cli.command()
@rdb_link_option
@sanity_check_folder_option
@venv_option
@dry_run_option
@slurm_override_option
@click.pass_obj
def check(
    site,
    rdb_link,
    sanity_check_folder,
    venv,
    dry_run,
    slurm_override,
):
    """Run sanity check on a data block."""
    cbid, token = _extract_cbid_and_token_from_rdb_link(rdb_link)

    # Check that the context folder exists, creating the directory if needed
    (sanity_check_folder / f"{cbid}").mkdir(parents=True, exist_ok=True)

    # Check that path to slurm log file exists. If not create it.
    _ensure_job_dirs()

    header(f"Running sanity check for CBID: {cbid}")
    console.print(f"  Sanity check folder: [cyan]{sanity_check_folder}[/cyan]")

    _run_data_jobs(
        ["sanity-check"],
        cbid,
        None,
        None,
        None,
        None,
        site,
        token=token,
        context_folder=sanity_check_folder,
        venv_path=venv,
        dry_run=dry_run,
        slurm_override=slurm_override,
    )
