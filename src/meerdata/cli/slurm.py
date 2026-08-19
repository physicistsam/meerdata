"""Job-step bodies, SLURM sbatch wrapping/submission, and local execution."""

import os
import subprocess
from pathlib import Path

from museek.cli.slurm_utils import merge_slurm_options
from rich.syntax import Syntax

from meerdata.cli.common import venv_activate_command
from meerdata.cli.console import console, header, success, warning


def _print_script(content: str) -> None:
    """Print an sbatch/local-command body with bash syntax highlighting."""
    console.print(Syntax(content, "bash", background_color="default"))


STEP_JOB_NAMES = {
    "download": "download_MVF",
    "auto": "ext_autos",
    "ms": "ext_MS",
    "cleanup": "cleanup",
    "sanity-check": "sanity-check",
}
STEP_EXTRA_SLURM_OPTIONS = {
    "sanity-check": ["--requeue"],
}
LOCAL_RUN_ORDER = ["download", "sanity-check", "auto", "ms", "cleanup"]


def _build_step_bodies(
    steps,
    cbid,
    dest,
    full_tmp_dest,
    ms_path,
    local_rdb,
    cpus_by_step,
    rdb_link=None,
    token=None,
    context_folder=None,
    venv_path=None,
):
    """Build the plain shell-command body for each requested step.

    Bodies are scheduler-agnostic: no SLURM directives, environment-module
    loads, or job-requeue logic. Those are layered on separately in
    `_wrap_for_slurm` when submitting to SLURM.

    Args:
        steps: List of steps to build bodies for
               ('download', 'auto', 'ms', 'cleanup', 'sanity-check')
        cbid: Block ID
        dest: Destination directory for extracted data
        full_tmp_dest: Full temporary destination directory (for cleanup)
        ms_path: Path for measurement set output
        local_rdb: Path to local RDB file
        cpus_by_step: Mapping of step name to worker/thread count to use
        rdb_link: Optional RDB link for download (required if 'download' in steps)
        token: Optional token for sanity check (required if 'sanity-check' in steps)
        context_folder: Optional context folder for sanity check
                       (required if 'sanity-check' in steps)
        venv_path: Optional venv path for sanity check
                  (required if 'sanity-check' in steps)
    """
    bodies = {}
    python_source = (
        venv_activate_command(venv_path)
        if venv_path
        else "source ./venv/meerdata/bin/activate"
    )

    if "download" in steps:
        if not rdb_link:
            raise ValueError("rdb_link is required when 'download' step is included")

        cpus = cpus_by_step.get("download", 1)
        bodies["download"] = f"""{python_source}
export OMP_NUM_THREADS={cpus}

RDB_LINK="{rdb_link}"
fulldest={full_tmp_dest}

which rclone
echo $RDB_LINK
echo $fulldest

mvf_download.py --workers={cpus} "$RDB_LINK" $fulldest --stats=15m --stats-one-line"""

    if "auto" in steps:
        cpus = cpus_by_step.get("auto", 1)
        bodies["auto"] = f"""export OMP_NUM_THREADS={cpus}

{python_source}

localRDB={local_rdb}
dest={dest}

echo running mvf_copy
echo $localRDB
echo $dest

mvf_copy.py --corrprods=auto --workers={cpus} $localRDB $dest"""

    if "ms" in steps:
        bodies["ms"] = f"""export OMP_NUM_THREADS={cpus_by_step.get("ms", 1)}

{python_source}

localRDB={local_rdb}
MS={ms_path}

echo running mvftoms.py
echo $localRDB
echo $MS

mvftoms.py -o $MS -v -f $localRDB"""

    if "cleanup" in steps:
        bodies["cleanup"] = f"rm -r {full_tmp_dest}"

    if "sanity-check" in steps:
        if not token or not context_folder or not venv_path:
            raise ValueError(
                "token, context_folder, and venv_path are required when "
                "'sanity-check' step is included"
            )

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
                "--InPlugin-load-visibilities-auto=False",
                "museek.config.sanity_check",
            ]
        )
        python_env = venv_activate_command(venv_path)

        bodies["sanity-check"] = f"""{python_env}
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

    return bodies


def _extract_option_value(options, flag):
    """Find `--flag=value` in a list of sbatch option strings and return value."""
    prefix = f"{flag}="
    for opt in options:
        if opt.startswith(prefix):
            return opt[len(prefix) :]
    return None


def _resolve_step_cpus(site, step, slurm_override=None):
    """Effective --cpus-per-task for a step, including any --slurm-override."""
    merged = merge_slurm_options(site.slurm.options, site.slurm.resources.get(step, []))
    merged = merge_slurm_options(merged, list(slurm_override or []))
    value = _extract_option_value(merged, "--cpus-per-task")
    return int(value) if value else 1


def _create_sbatch_script(
    job_name,
    cbid,
    site_options=None,
    step_options=None,
    extra_options=None,
    script_body="",
    slurm_override=None,
):
    """Create a standardized SLURM sbatch script.

    Directives are merged with increasing priority: base (nodes/job-name/
    output) < site-wide `slurm.options` < step-specific `slurm.resources` <
    step-fixed `extra_options` (e.g. --requeue) < `-s`/`--slurm-override`.
    """
    base_options = [
        "--nodes=1",
        "--ntasks-per-node=1",
        f"--job-name={job_name}-{cbid}",
        "--output=logs/%x-%j.out",
    ]
    options = merge_slurm_options(base_options, site_options or [])
    options = merge_slurm_options(options, step_options or [])
    options = merge_slurm_options(options, extra_options or [])
    options = merge_slurm_options(options, list(slurm_override or []))

    sbatch_header = "\n".join(f"#SBATCH {opt}" for opt in options)

    return f"""#!/bin/bash
{sbatch_header}

{script_body}
"""


def _wrap_for_slurm(step, body, cbid, site, slurm_override=None):
    """Wrap a plain step body into a full sbatch script using site.slurm config."""
    if step == "download" and site.slurm.modules:
        module_lines = "\n".join(f"module load {m}" for m in site.slurm.modules)
        body = f"{module_lines}\n{body} || {site.slurm.scontrol_path} requeue $SLURM_JOB_ID"

    return _create_sbatch_script(
        STEP_JOB_NAMES[step],
        cbid,
        site_options=site.slurm.options,
        step_options=site.slurm.resources.get(step, []),
        extra_options=STEP_EXTRA_SLURM_OPTIONS.get(step),
        script_body=body,
        slurm_override=slurm_override,
    )


def _submit_job(script_path, dependency=None):
    """Submit a SLURM job and return the job ID."""
    cmd = ["sbatch"]
    if dependency:
        cmd.extend(["-d", dependency, "--kill-on-invalid-dep=yes"])
    cmd.append(str(script_path))

    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return result.stdout.strip().split()[-1]


def _submit_slurm_jobs(scripts, cbid, dry_run=False):
    """Write sbatch scripts and submit jobs with proper dependencies.

    Args:
        scripts: Dictionary of step name to rendered sbatch script content
        cbid: Block ID
        dry_run: If True, create scripts but don't submit jobs
    """
    sbatch_dir = Path("./sbatch")
    sbatch_dir.mkdir(parents=True, exist_ok=True)

    # Write scripts to files
    script_files = {}
    for script_type, content in scripts.items():
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
        success(f"Created sbatch script: {script_files[script_type]}")
        if dry_run:
            _print_script(content)

    if dry_run:
        warning("Dry run mode: Scripts created but not submitted")
        return

    # Submit jobs with proper dependencies
    job_ids = []
    download_id = None

    if "download" in script_files:
        download_id = _submit_job(script_files["download"])
        job_ids.append(download_id)
        success(f"Submitted download job: {download_id}")

    if "sanity-check" in script_files:
        sanity_id = _submit_job(script_files["sanity-check"])
        job_ids.append(sanity_id)
        success(f"Submitted sanity check job: {sanity_id}")

    extraction_jobs = []
    dependency = f"afterok:{download_id}" if download_id else None

    if "auto" in script_files:
        auto_id = _submit_job(script_files["auto"], dependency)
        extraction_jobs.append(auto_id)
        job_ids.append(auto_id)
        success(f"Submitted auto extraction job: {auto_id}")

    if "ms" in script_files:
        ms_id = _submit_job(script_files["ms"], dependency)
        extraction_jobs.append(ms_id)
        job_ids.append(ms_id)
        success(f"Submitted MS extraction job: {ms_id}")

    if "cleanup" in script_files:
        if extraction_jobs:
            cleanup_dependency = ":".join(extraction_jobs)
            cleanup_id = _submit_job(
                script_files["cleanup"], f"afterok:{cleanup_dependency}"
            )
        else:
            cleanup_dependency = f"afterok:{download_id}" if download_id else None
            cleanup_id = _submit_job(script_files["cleanup"], cleanup_dependency)

        job_ids.append(cleanup_id)
        success(f"Submitted cleanup job: {cleanup_id}")

    header(f"All jobs submitted with IDs: {','.join(job_ids)}")


def _run_local_steps(step_bodies, dry_run=False):
    """Run job steps directly as foreground subprocesses, no SLURM involved."""
    for step in LOCAL_RUN_ORDER:
        if step not in step_bodies:
            continue
        body = step_bodies[step]
        if dry_run:
            header(f"{step} (dry run, not executed)")
            _print_script(body)
            continue
        header(f"Running {step} step locally...")
        subprocess.run(["bash", "-c", body], check=True)

    if dry_run:
        warning("Dry run mode: commands printed but not executed")
    else:
        success("All steps completed")


def _run_data_jobs(
    steps,
    cbid,
    dest,
    full_tmp_dest,
    ms_path,
    local_rdb,
    site,
    rdb_link=None,
    token=None,
    context_folder=None,
    venv_path=None,
    dry_run=False,
    slurm_override=None,
):
    """Build step bodies and either submit them to SLURM or run them locally."""
    if slurm_override and site.scheduler != "slurm":
        warning(
            "--slurm-override is ignored because the resolved site's "
            f'scheduler is "{site.scheduler}".'
        )

    if site.scheduler == "slurm":
        cpus_by_step = {
            step: _resolve_step_cpus(site, step, slurm_override) for step in steps
        }
    else:
        cpus_by_step = dict.fromkeys(steps, os.cpu_count() or 1)

    step_bodies = _build_step_bodies(
        steps,
        cbid,
        dest,
        full_tmp_dest,
        ms_path,
        local_rdb,
        cpus_by_step,
        rdb_link=rdb_link,
        token=token,
        context_folder=context_folder,
        venv_path=venv_path,
    )

    if site.scheduler == "local":
        _run_local_steps(step_bodies, dry_run)
        return

    scripts = {
        step: _wrap_for_slurm(step, body, cbid, site, slurm_override)
        for step, body in step_bodies.items()
    }
    _submit_slurm_jobs(scripts, cbid, dry_run)
