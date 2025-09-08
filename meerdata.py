#!/usr/bin/env python3
from pathlib import Path
import click
import subprocess


CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"], "max_content_width": 100}


rdb_link_option = click.option(
    '-r', '--rdb-link', required=True, help='SARAO Archive RDB file link (full url).'
)


def _validate_venv(ctx, param, value):
    def_err = "You can execute the `setup.sh` bash script in the repository to set one up."
    if not value.exists():
        raise FileNotFoundError(
            f"Python virtual environment directory {value} does not exists. {def_err}"
        )
    if not (value / "bin/activate").exists():
        raise RuntimeError(
            f"{value} does not seem to be a Python virtual environment. {def_err}"
        )
    return value


def _extract_cbid_and_token_from_rdb_link(rdb_link):
    """Extract CBID and token from RDB link URL."""
    if not rdb_link.startswith('http'):
        raise click.ClickException("RDB link must be a valid URL starting with http")
    
    # Extract CBID from URL path (e.g., /1756679237/1756679237_sdp_l0.full.rdb)
    try:
        cbid = rdb_link.split('/')[3]  # https://archive-gw-1.kat.ac.za/1756679237/...
    except IndexError:
        raise click.ClickException("Invalid RDB link format: cannot extract CBID")
    
    # Extract token from query parameter
    if '?token=' not in rdb_link:
        raise click.ClickException("RDB link must contain a token parameter")
    
    token = rdb_link.split('?token=')[1]
    
    return cbid, token


def _create_sbatch_script(job_name, cbid, cpus, mem, time, account="b205-meerklass-ag", 
                         partition="Main", additional_directives="", script_body=""):
    """Create a standardized SLURM sbatch script.
    
    The SBATCH header is mostly fixed although the resource allocation will be adjusted
    based on the passing parameters.
    """
    return f"""#!/bin/bash
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task={cpus}
#SBATCH --mem={mem}
#SBATCH --job-name={job_name}-{cbid}
#SBATCH --output=logs/%x-%j.out
{additional_directives}
#SBATCH --partition={partition}
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


def _create_pull_scripts(rdb_link, cbid, dest, full_dest, ms_path, local_rdb):
    """Create all sbatch scripts needed for data pulling."""
    scripts = {}
    
    python_source = "source ./venv/meerdata/bin/activate"

    # Download script
    download_body = f"""{python_source}
module load rclone
export OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK

RDB_LINK="{rdb_link}"
dest={full_dest}

which rclone
echo $RDB_LINK
echo $dest

mvf_download.py --workers=$SLURM_CPUS_PER_TASK "$RDB_LINK" $dest --stats=15m --stats-one-line || /opt/slurm/bin/scontrol requeue $SLURM_JOB_ID"""
    
    scripts['download'] = _create_sbatch_script(
        "download_MVF", cbid, 8, "16GB", "48:00:00", script_body=download_body
    )
    
    # Auto extraction script
    auto_body = f"""export OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK

{python_source}

localRDB={local_rdb}
dest={dest}

echo running mvf_copy
echo $localRDB
echo $dest

mvf_copy.py --corrprods=auto --workers=$SLURM_CPUS_PER_TASK $localRDB $dest"""
    
    scripts['auto'] = _create_sbatch_script(
        "ext_autos", cbid, 30, "50GB", "00:45:00", script_body=auto_body
    )
    
    # MS extraction script
    ms_body = f"""export OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK

{python_source}

localRDB={local_rdb}
MS={ms_path}

echo running mvftoms
echo $localRDB
echo $MS

python mvftoms-OTF-patch.py -o $MS -v -f $localRDB"""
    
    scripts['ms'] = _create_sbatch_script(
        "ext_MS", cbid, 24, "50GB", "02:00:00", 
        additional_directives="#SBATCH --error=logs/%x-%j.err",
        script_body=ms_body
    )
    
    # Cleanup script
    cleanup_body = f"rm -r {full_dest}"
    scripts['cleanup'] = _create_sbatch_script(
        "cleanup", cbid, 1, "1GB", "0:30:00", script_body=cleanup_body
    )
    
    return scripts


def _create_sanity_check_script(cbid, token, data_folder, context_folder, venv_path):
    """Create the sanity check sbatch script."""
    # Set up museek command line
    museek_cmd = " ".join(
        [
            "museek",
            f"--InPlugin-block-name={cbid}",
            f"--InPlugin-token={token}" if token is not None else "",
            f"--InPlugin-data-folder={data_folder}" if data_folder is not None else "",
            f"--InPlugin-context-folder={context_folder}",
            "museek.config.sanity_check",
        ]
    )
    python_env = f"source {venv_path}/bin/activate"

    return f"""#!/bin/bash

#SBATCH --job-name='sanity-check-{cbid}'
#SBATCH --output=logs/sanity-check-{cbid}-%j.log
#SBATCH --account=b205-meerklass-ag
#SBATCH --partition=Main
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=10GB
#SBATCH --time=00:05:00
#SBATCH --requeue

{python_env}
echo "Using Python Environment: $(which python)"

export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1

# Get museek path and dump the template config for the sake of documenting the run
echo "==== museek sanity check pipeline ===="
config_file=$(python -c "import museek; print(museek.__path__[0])")/config/sanity_check.py
echo "museek config file: ${{config_file}}"
echo "---- beginning of config file ----"
cat ${{config_file}}

echo "---- run parameters ----"
echo "Block Number: {cbid}"
echo "Token: {token}"
echo "Context folder: {context_folder}"
echo "Data folder: {data_folder}"

echo "Executing command: {museek_cmd}"

{museek_cmd}
"""


def _write_and_submit_pull_jobs(scripts, correlation, cbid):
    """Write sbatch scripts to files and submit jobs based on correlation type."""
    # Create sbatch directory if it doesn't exist
    sbatch_dir = Path("./sbatch")
    sbatch_dir.mkdir(parents=True, exist_ok=True)
    
    # Write scripts to files
    script_files = {}
    for script_type, content in scripts.items():
        filename = f"local_extract_{script_type}-{cbid}.sbatch" if script_type in ['auto', 'ms'] else f"{script_type}_MVF-{cbid}.sbatch" if script_type == 'download' else f"{script_type}-{cbid}.sbatch"
        script_files[script_type] = sbatch_dir / filename
        with open(script_files[script_type], "w") as f:
            f.write(content)
    
    # Submit jobs
    job_ids = []
    
    # Submit download job first
    download_id = _submit_job(script_files['download'])
    job_ids.append(download_id)
    click.echo(f"Submitted download job: {download_id}")
    
    extraction_jobs = []
    
    if correlation in ['auto', 'all']:
        auto_id = _submit_job(script_files['auto'], f"afterok:{download_id}")
        extraction_jobs.append(auto_id)
        click.echo(f"Submitted auto extraction job: {auto_id}")
    
    if correlation in ['cross', 'all']:
        ms_id = _submit_job(script_files['ms'], f"afterok:{download_id}")
        extraction_jobs.append(ms_id)
        click.echo(f"Submitted MS extraction job: {ms_id}")
    
    # Submit cleanup job after all extraction jobs
    if extraction_jobs:
        dependency = ":".join(extraction_jobs)
        cleanup_id = _submit_job(script_files['cleanup'], f"afterok:{dependency}")
        job_ids.extend(extraction_jobs)
        job_ids.append(cleanup_id)
        click.echo(f"Submitted cleanup job: {cleanup_id}")
    
    return job_ids


@click.group(
    context_settings=CONTEXT_SETTINGS, 
    epilog="Run `python meerdata.py COMMAND -h` for more details."
)
def cli():
    """MeerKLASS data management tool."""
    pass


@cli.command()
@rdb_link_option
@click.option(
    "-c",
    "--correlation",
    type=click.Choice(['auto', 'cross', 'all']),
    default='auto',
    show_default=True,
    help="Type of correlation data to pull: auto (autocorrelations), "
    "cross (OTF measurement set), all (both)"
)
@click.option(
    "--data-folder",
    type=click.Path(exists=True, resolve_path=True, path_type=Path),
    default="/idia/projects/meerklass/MEERKLASS-1/uhf_data/XLP2025/raw",
    show_default=True,
    help="Directory for storing the data"
)
def pull(rdb_link, correlation, data_folder):
    """Download the data block."""
    cbid, token = _extract_cbid_and_token_from_rdb_link(rdb_link)
    
    # Set up directories
    dest = data_folder / cbid
    full_dest = Path(str(data_folder).replace('/raw', '/raw_full')) / cbid
    ms_path = dest / f"{cbid}_sdp_l0.ms"
    local_rdb = full_dest / cbid / f"{cbid}_sdp_l0.full.rdb"
    
    # Create directories
    Path("./logs").mkdir(parents=True, exist_ok=True)
    dest.mkdir(parents=True, exist_ok=True)
    full_dest.mkdir(parents=True, exist_ok=True)
    
    click.echo(f"Pulling {correlation} correlation data for CBID: {cbid}")
    click.echo(f"Destination: {dest}")
    
    # Create and submit jobs
    scripts = _create_pull_scripts(rdb_link, cbid, dest, full_dest, ms_path, local_rdb)
    job_ids = _write_and_submit_pull_jobs(scripts, correlation, cbid)
    
    click.echo(f"All jobs submitted with IDs: {','.join(job_ids)}")


@cli.command()
@rdb_link_option
@click.option(
    "--context-folder",
    required=True,
    type=click.Path(exists=True, resolve_path=True, path_type=Path),
    default="/idia/projects/meerklass/MEERKLASS-1/uhf_data/XLP2025/sanity_checks",
    show_default=True,
    help="Context folder to save sanity check results.",
)
@click.option(
    "--venv-path",
    type=click.Path(exists=False, resolve_path=True, path_type=Path),
    default="./venv/meerdata",
    show_default=True,
    callback=_validate_venv,
    help="Path to the Python virtual environment to use.",
)
def check(
    rdb_link,
    context_folder,
    venv_path,
):
    """Run sanity check on the data block."""    
    # Validate inputs and extract block_number/token
    cbid, token = _extract_cbid_and_token_from_rdb_link(rdb_link)

    # Check that the context folder exists, creating the directory if needed
    (context_folder / f"{cbid}").mkdir(parents=True, exist_ok=True)

    # Check that path to slurm log file exists. If not create it.
    Path("./logs").mkdir(parents=True, exist_ok=True)
    Path("./sbatch").mkdir(parents=True, exist_ok=True)

    # Create and write the sbatch script
    program = _create_sanity_check_script(
        cbid, token, "", context_folder, venv_path
    )
    
    sbatch_file = Path(f"./sbatch/sanity-check-{cbid}.sbatch").resolve()
    with open(sbatch_file, "w") as fl:
        click.echo(f"==> Generating an sbatch script, saving it to {sbatch_file}")
        click.echo("-------BEGINNING OF SBATCH-------")
        click.echo(program)
        click.echo("-------END OF SBATCH-------")
        fl.write(program)
    
    click.echo(f"==> Submitting the SBATCH script")
    subprocess.run(["sbatch", f"{sbatch_file.as_posix()}"], check=True)


if __name__ == "__main__":
    cli()