#!/usr/bin/env python3
import subprocess
from pathlib import Path

import click

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"], "max_content_width": 100}
PATH_DW = click.Path(
    exists=True,
    resolve_path=True,
    writable=True,
    file_okay=False,
    dir_okay=True,
    path_type=Path,
)

rdb_link_option = click.option(
    "-r", "--rdb-link", required=True, help="SARAO Archive RDB file link (full url)."
)
dry_run_option = click.option(
    "--dry-run",
    is_flag=True,
    help="Create sbatch scripts but do not submit them and exit the program",
)
data_folder_option = click.option(
    "--data-folder",
    type=PATH_DW,
    default="/idia/projects/meerklass/MEERKLASS-1/uhf_data/XLP2025/raw",
    show_default=True,
    help="Directory for storing the extracted data",
)
mail_user_option = click.option(
    "--mail-user",
    type=str,
    default=None,
    help="Email address to receive SLURM job notifications",
)
mail_type_option = click.option(
    "--mail-type",
    type=str,
    default=None,
    help="Notification types for SLURM jobs (e.g., BEGIN,END,FAIL). "
    "See https://slurm.schedmd.com/sbatch.html#OPT_mail-type for all choices",
)

# venv_option is defined after _validate_venv so the callback can be referenced

use_patched_mvftoms_option = click.option(
    "--use-patched-mvftoms",
    is_flag=True,
    default=False,
    help=(
        "Use the patched mvftoms_otf_patch.py instead of the default "
        "katdal-provided mvftoms.py. WARNING: this patched version is deprecated "
        "and will be removed in the next release."
    ),
)


def _validate_venv(ctx, param, value):
    def_err = "See README.md for installation instruction."
    if not value.exists():
        raise FileNotFoundError(
            f"Python virtual environment directory {value} does not exists. {def_err}"
        )
    if not (value / "bin/activate").exists():
        raise RuntimeError(
            f"{value} does not seem to be a Python virtual environment. {def_err}"
        )
    return value

venv_option = click.option(
    "--venv",
    type=click.Path(exists=False, resolve_path=True, path_type=Path),
    default="/idia/projects/meerklass/virtualenv/meerklass",
    show_default=True,
    callback=_validate_venv,
    help=(
        "Path to the Python virtual environment to use. "
        "The specified venv will be activated in generated sbatch scripts "
        "via `source {venv}/bin/activate`."
    ),
)


def _extract_cbid_and_token_from_rdb_link(rdb_link):
    """Extract CBID and token from RDB link URL."""
    if not rdb_link.startswith("http"):
        raise click.ClickException("RDB link must be a valid URL starting with http")

    # Extract CBID from URL path (e.g., /1756679237/1756679237_sdp_l0.full.rdb)
    try:
        cbid = rdb_link.split("/")[3]  # https://archive-gw-1.kat.ac.za/1756679237/...
    except IndexError:
        raise click.ClickException("Invalid RDB link format: cannot extract CBID")

    # Extract token from query parameter
    if "?token=" not in rdb_link:
        raise click.ClickException("RDB link must contain a token parameter")

    token = rdb_link.split("?token=")[1]

    return cbid, token


def _create_sbatch_script(
    job_name,
    cbid,
    cpus,
    mem,
    time,
    account="b205-meerklass-ag",
    partition="Main",
    additional_directives="",
    script_body="",
    mail_user=None,
    mail_type=None,
):
    """Create a standardized SLURM sbatch script.

    The SBATCH header is mostly fixed although the resource allocation will be adjusted
    based on the passing parameters.
    """
    mail_directives = ""
    if mail_user:
        mail_directives += f"#SBATCH --mail-user={mail_user}\n"
    if mail_type:
        mail_directives += f"#SBATCH --mail-type={mail_type}\n"

    return f"""#!/bin/bash
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task={cpus}
#SBATCH --mem={mem}
#SBATCH --job-name={job_name}-{cbid}
#SBATCH --output=logs/%x-%j.out
{additional_directives}{mail_directives}#SBATCH --partition={partition}
#SBATCH --time={time}
#SBATCH --account={account}

{script_body}
"""


def _submit_job(script_path, dependency=None):
    """Submit a SLURM job and return the job ID."""
    cmd = ["sbatch"]
    if dependency:
        cmd.extend(["-d", dependency, "--kill-on-invalid-dep=yes"])
    cmd.append(str(script_path))

    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return result.stdout.strip().split()[-1]


def _create_data_scripts(
    steps,
    cbid,
    dest,
    full_dest,
    ms_path,
    local_rdb,
    rdb_link=None,
    token=None,
    context_folder=None,
    venv_path=None,
    use_patched_mvftoms=False,
    mail_user=None,
    mail_type=None,
):
    """Create sbatch scripts for specified data processing steps.

    Args:
        steps: List of steps to create scripts for
               ('download', 'auto', 'ms', 'cleanup', 'sanity-check')
        cbid: Block ID
        dest: Destination directory for extracted data
        full_dest: Full destination directory (for cleanup)
        ms_path: Path for measurement set output
        local_rdb: Path to local RDB file
        rdb_link: Optional RDB link for download (required if 'download' in steps)
        token: Optional token for sanity check (required if 'sanity-check' in steps)
        context_folder: Optional context folder for sanity check
                       (required if 'sanity-check' in steps)
        venv_path: Optional venv path for sanity check
                  (required if 'sanity-check' in steps)
        use_patched_mvftoms: Use the patched mvftoms_otf_patch.py instead of the
                             default katdal-provided mvftoms.py. When True a
                             deprecation warning will be emitted.
        mail_user: Optional email address for SLURM notifications
        mail_type: Optional notification types for SLURM jobs
    """
    scripts = {}
    python_source = f"source {venv_path}/bin/activate" if venv_path else "source ./venv/meerdata/bin/activate"

    # Download script
    if "download" in steps:
        if not rdb_link:
            raise ValueError("rdb_link is required when 'download' step is included")

        download_body = f"""{python_source}
module load rclone
export OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK

RDB_LINK="{rdb_link}"
fulldest={full_dest}

which rclone
echo $RDB_LINK
echo $dest

mvf_download.py --workers=$SLURM_CPUS_PER_TASK "$RDB_LINK" $fulldest \\
    --stats=15m --stats-one-line || /opt/slurm/bin/scontrol requeue $SLURM_JOB_ID"""

        scripts["download"] = _create_sbatch_script(
            "download_MVF",
            cbid,
            8,
            "16GB",
            "48:00:00",
            script_body=download_body,
            mail_user=mail_user,
            mail_type=mail_type,
        )

    # Auto extraction script
    if "auto" in steps:
        auto_body = f"""export OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK

{python_source}

localRDB={local_rdb}
dest={dest}

echo running mvf_copy
echo $localRDB
echo $dest

mvf_copy.py --corrprods=auto --workers=$SLURM_CPUS_PER_TASK $localRDB $dest"""

        scripts["auto"] = _create_sbatch_script(
            "ext_autos",
            cbid,
            30,
            "50GB",
            "00:45:00",
            script_body=auto_body,
            mail_user=mail_user,
            mail_type=mail_type,
        )

    # MS extraction script
    if "ms" in steps:
        # Use the katdal-provided mvftoms.py by default; use the patched version only
        # when explicitly requested via `use_patched_mvftoms`.
        mvftoms_script = "mvftoms.py"
        ms_warning = ""
        if use_patched_mvftoms:
            mvftoms_script = "mvftoms_otf_patch.py"
            ms_warning = (
                'echo "WARNING: Using patched mvftoms_otf_patch.py; this '
                "patched version is deprecated and will be "
                'removed in the next release."\n'
            )

        ms_body = f"""export OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK

{python_source}

localRDB={local_rdb}
MS={ms_path}

{ms_warning}echo running {mvftoms_script}
echo $localRDB
echo $MS

python {mvftoms_script} -o $MS -v -f $localRDB"""

        scripts["ms"] = _create_sbatch_script(
            "ext_MS",
            cbid,
            24,
            "50GB",
            "06:00:00",
            script_body=ms_body,
            mail_user=mail_user,
            mail_type=mail_type,
        )

    # Cleanup script
    if "cleanup" in steps:
        cleanup_body = f"rm -r {full_dest}"
        scripts["cleanup"] = _create_sbatch_script(
            "cleanup",
            cbid,
            1,
            "1GB",
            "0:30:00",
            script_body=cleanup_body,
            mail_user=mail_user,
            mail_type=mail_type,
        )

    # Sanity check script
    if "sanity-check" in steps:
        if not token or not context_folder or not venv_path:
            raise ValueError(
                "token, context_folder, and venv_path are required when "
                "'sanity-check' step is included"
            )

        # Set up museek command line
        data_folder_arg = (
            "--InPlugin-data-folder="
            if dest is None
            else f"--InPlugin-data-folder={dest}"
        )
        museek_cmd = " ".join(
            [
                "museek",
                f"--InPlugin-block-name={cbid}",
                f"--InPlugin-token={token}" if token is not None else "",
                data_folder_arg,
                f"--InPlugin-context-folder={context_folder}",
                "museek.config.sanity_check",
            ]
        )
        python_env = f"source {venv_path}/bin/activate"

        sanity_body = f"""{python_env}
echo "Using Python Environment: $(which python)"

export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1

# Get museek path and dump the template config for the sake of documenting the run
echo "==== museek sanity check pipeline ===="
config_file=$(python -c "import museek; \\
print(museek.__path__[0])")/config/sanity_check.py
echo "museek config file: ${{config_file}}"
echo "---- beginning of config file ----"
cat ${{config_file}}

echo "---- run parameters ----"
echo "Block Number: {cbid}"
echo "Token: {token}"
echo "Context folder: {context_folder}"
echo "Data folder: {dest}"

echo "Executing command: {museek_cmd}"

{museek_cmd}"""

        scripts["sanity-check"] = _create_sbatch_script(
            "sanity-check",
            cbid,
            1,
            "4GB",
            "00:08:00",
            additional_directives="#SBATCH --requeue",
            script_body=sanity_body,
            mail_user=mail_user,
            mail_type=mail_type,
        )

    return scripts


def _write_and_submit_data_jobs(scripts, cbid, dry_run=False):
    """Write sbatch scripts and submit jobs with proper dependencies.

    Args:
        scripts: Dictionary of script types and their content
                (only contains requested steps)
        cbid: Block ID
        dry_run: If True, create scripts but don't submit jobs
    """
    # Create sbatch directory if it doesn't exist
    sbatch_dir = Path("./sbatch")
    sbatch_dir.mkdir(parents=True, exist_ok=True)

    # Write scripts to files
    script_files = {}
    for script_type, content in scripts.items():
        # Determine filename based on script type
        if script_type == "download":
            filename = f"download_MVF-{cbid}.sbatch"
        elif script_type in ["auto", "ms"]:
            filename = f"local_extract_{script_type}-{cbid}.sbatch"
        elif script_type == "sanity-check":
            filename = f"sanity-check-{cbid}.sbatch"
        else:  # cleanup
            filename = f"{script_type}-{cbid}.sbatch"

        script_files[script_type] = sbatch_dir / filename
        with open(script_files[script_type], "w") as f:
            f.write(content)
        click.echo(f"Created sbatch script: {script_files[script_type]}")

    if dry_run:
        click.echo("Dry run mode: Scripts created but not submitted")
        return []

    # Submit jobs with proper dependencies
    job_ids = []
    download_id = None

    # Submit download job first if present
    if "download" in script_files:
        download_id = _submit_job(script_files["download"])
        job_ids.append(download_id)
        click.echo(f"Submitted download job: {download_id}")

    # Submit sanity check job (independent, no dependencies)
    if "sanity-check" in script_files:
        sanity_id = _submit_job(script_files["sanity-check"])
        job_ids.append(sanity_id)
        click.echo(f"Submitted sanity check job: {sanity_id}")

    # Submit extraction jobs (depend on download if present)
    extraction_jobs = []
    dependency = f"afterok:{download_id}" if download_id else None

    if "auto" in script_files:
        auto_id = _submit_job(script_files["auto"], dependency)
        extraction_jobs.append(auto_id)
        job_ids.append(auto_id)
        click.echo(f"Submitted auto extraction job: {auto_id}")

    if "ms" in script_files:
        ms_id = _submit_job(script_files["ms"], dependency)
        extraction_jobs.append(ms_id)
        job_ids.append(ms_id)
        click.echo(f"Submitted MS extraction job: {ms_id}")

    # Submit cleanup job after all extraction jobs
    if "cleanup" in script_files:
        if extraction_jobs:
            cleanup_dependency = ":".join(extraction_jobs)
            cleanup_id = _submit_job(
                script_files["cleanup"], f"afterok:{cleanup_dependency}"
            )
        else:
            # No extraction jobs, cleanup depends on download or runs immediately
            cleanup_dependency = f"afterok:{download_id}" if download_id else None
            cleanup_id = _submit_job(script_files["cleanup"], cleanup_dependency)

        job_ids.append(cleanup_id)
        click.echo(f"Submitted cleanup job: {cleanup_id}")

    return job_ids


@click.group(
    context_settings=CONTEXT_SETTINGS,
    epilog="Run `python meerdata.py COMMAND -h` for more details.",
)
def cli():
    """MeerKLASS data management tool."""
    pass


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
@mail_user_option
@mail_type_option
@dry_run_option
@use_patched_mvftoms_option
@venv_option
@click.option(
    "--no-cleanup",
    is_flag=True,
    help="Skip the full raw data cleanup step at the end",
)
def pull(
    rdb_link,
    correlation,
    data_folder,
    mail_user,
    mail_type,
    dry_run,
    use_patched_mvftoms,
    venv,
    no_cleanup,
):
    """Download a data block."""
    cbid, token = _extract_cbid_and_token_from_rdb_link(rdb_link)

    # Set up directories
    dest = data_folder / cbid
    full_dest = Path(str(data_folder).replace("/raw", "/raw_full")) / cbid
    ms_path = dest / f"{cbid}_sdp_l0.ms"
    local_rdb = full_dest / cbid / f"{cbid}_sdp_l0.full.rdb"

    # Create directories
    Path("./logs").mkdir(parents=True, exist_ok=True)
    dest.mkdir(parents=True, exist_ok=True)
    full_dest.mkdir(parents=True, exist_ok=True)

    if use_patched_mvftoms:
        click.echo(
            "WARNING: Using patched mvftoms_otf_patch.py; this patched version is deprecated and will be removed in the next release."
        )

    click.echo(f"Pulling {correlation} correlation data for CBID: {cbid}")
    click.echo(f"Destination: {dest}")

    # Determine which steps to run based on correlation type
    steps = ["download"]  # Always download for pull command
    if correlation in ["auto", "all"]:
        steps.append("auto")
    if correlation in ["cross", "all"]:
        steps.append("ms")
    if not no_cleanup:
        steps.append("cleanup")  # Cleanup at the end unless --no-cleanup is specified

    # Create and submit jobs
    scripts = _create_data_scripts(
        steps,
        cbid,
        dest,
        full_dest,
        ms_path,
        local_rdb,
        rdb_link,
        venv_path=venv,
        use_patched_mvftoms=use_patched_mvftoms,
        mail_user=mail_user,
        mail_type=mail_type,
    )
    job_ids = _write_and_submit_data_jobs(scripts, cbid, dry_run)

    if dry_run:
        click.echo("Dry run completed: All sbatch scripts created")
    else:
        click.echo(f"All jobs submitted with IDs: {','.join(job_ids)}")


@cli.command()
@rdb_link_option
@click.option(
    "--context-folder",
    required=True,
    type=PATH_DW,
    default="/idia/projects/meerklass/MEERKLASS-1/uhf_data/XLP2025/sanity_checks",
    show_default=True,
    help="Context folder to save sanity check results.",
)
@venv_option
@mail_user_option
@mail_type_option
@dry_run_option
def check(
    rdb_link,
    context_folder,
    venv,
    mail_user,
    mail_type,
    dry_run,
):
    """Run sanity check on a data block."""
    # Validate inputs and extract block_number/token
    cbid, token = _extract_cbid_and_token_from_rdb_link(rdb_link)

    # Check that the context folder exists, creating the directory if needed
    (context_folder / f"{cbid}").mkdir(parents=True, exist_ok=True)

    # Check that path to slurm log file exists. If not create it.
    Path("./logs").mkdir(parents=True, exist_ok=True)
    Path("./sbatch").mkdir(parents=True, exist_ok=True)

    click.echo(f"Running sanity check for CBID: {cbid}")
    click.echo(f"Context folder: {context_folder}")

    # Create and submit the sanity check job
    steps = ["sanity-check"]
    scripts = _create_data_scripts(
        steps,
        cbid,
        None,
        None,
        None,
        None,
        token=token,
        context_folder=context_folder,
        venv_path=venv,
        mail_user=mail_user,
        mail_type=mail_type,
    )
    job_ids = _write_and_submit_data_jobs(scripts, cbid, dry_run)

    if dry_run:
        click.echo("Dry run completed: Sanity check script created")
    else:
        click.echo(f"Sanity check job submitted with ID: {','.join(job_ids)}")


@cli.command()
@click.option(
    "-b",
    "--block-number",
    required=True,
    multiple=True,
    type=str,
    help="Block number(s) to verify. Can be specified multiple times.",
)
@click.option(
    "--context-folder",
    type=click.Path(exists=True, resolve_path=True, path_type=Path),
    default="/idia/projects/meerklass/MEERKLASS-1/uhf_data/XLP2025/raw",
    show_default=True,
    help="Context folder containing block directories.",
)
def verify(block_number, context_folder):
    """Verify existent and disk usage of data blocks."""
    click.echo(f"Verifying {len(block_number)} block(s) in {context_folder}")
    summary = []
    for bn in block_number:
        block_dir = context_folder / bn
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
            except Exception as e:
                size_gb = "ERR"
                click.echo(f"  [!] Error getting disk usage for {block_dir}: {e}")
            if size_gb == 0:
                click.echo(
                    f"  [WARNING] {block_dir} exists but is empty (disk usage: 0 GB)"
                )
            else:
                click.echo(f"  [OK] {block_dir} exists, disk usage: {size_gb} GB")
            summary.append((bn, True, size_gb))
        else:
            click.echo(f"  [MISSING] {block_dir} does not exist.")
            summary.append((bn, False, 0))
    # Print summary
    click.echo("\nSummary Report:")
    click.echo("Block Number | Exists | Disk Usage (GB)")
    click.echo("-------------|--------|----------------")
    for bn, exists, size_gb in summary:
        click.echo(f"{bn:<12} | {'YES' if exists else 'NO ':<6} | {size_gb}")


@cli.command()
@click.option(
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
@mail_user_option
@mail_type_option
@dry_run_option
@use_patched_mvftoms_option
@venv_option
def extract(
    rdb_file,
    correlation,
    data_folder,
    mail_user,
    mail_type,
    dry_run,
    use_patched_mvftoms,
    venv,
):
    """Extract auto or cross-correlation from local data."""
    # Infer cbid from file path (assume .../<cbid>_sdp_l0.full.rdb)
    cbid = rdb_file.stem.split("_")[0]

    # Set up output directories
    dest = data_folder / cbid
    full_dest = rdb_file.parent
    ms_path = dest / f"{cbid}_sdp_l0.ms"

    # Create output directories
    Path("./logs").mkdir(parents=True, exist_ok=True)
    Path("./sbatch").mkdir(parents=True, exist_ok=True)
    dest.mkdir(parents=True, exist_ok=True)

    if use_patched_mvftoms:
        click.echo(
            "WARNING: Using patched mvftoms_otf_patch.py; this patched version is deprecated and will be removed in the next release."
        )

    click.echo(f"Extracting {correlation} correlation data for CBID: {cbid}")
    click.echo(f"Source RDB: {rdb_file}")
    click.echo(f"Destination: {dest}")

    # Determine which steps to run based on correlation type (no download)
    steps = []
    if correlation in ["auto", "all"]:
        steps.append("auto")
    if correlation in ["cross", "all"]:
        steps.append("ms")
    steps.append("cleanup")  # Always cleanup at the end

    # Create and submit jobs
    scripts = _create_data_scripts(
        steps,
        cbid,
        dest,
        full_dest,
        ms_path,
        rdb_file,
        venv_path=venv,
        use_patched_mvftoms=use_patched_mvftoms,
        mail_user=mail_user,
        mail_type=mail_type,
    )
    job_ids = _write_and_submit_data_jobs(scripts, cbid, dry_run)

    if dry_run:
        click.echo("Dry run completed: All sbatch scripts created")
    else:
        click.echo(f"All jobs submitted with IDs: {','.join(job_ids)}")


if __name__ == "__main__":
    cli()
