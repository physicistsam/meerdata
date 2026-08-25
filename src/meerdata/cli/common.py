"""Shared CLI settings, option decorators, validators, and small helpers."""

import os
import urllib.parse
from pathlib import Path

import click

from meerdata.cli.console import warning

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"], "max_content_width": 100}
PATH_DW = click.Path(
    exists=True,
    resolve_path=True,
    writable=True,
    file_okay=False,
    dir_okay=True,
    path_type=Path,
)


def _ensure_writable(path):
    """Raise a ClickException if the current user cannot write to `path`."""
    if not os.access(path, os.W_OK):
        raise click.ClickException(f"No write permission for {path}.")


def _validate_sanity_check_folder(ctx, param, value):
    """Validate or infer the sanity check folder path for the resolved site.

    If not provided, use the resolved site's default if it exists; otherwise
    require the caller to provide an explicit `--sanity-check-folder` path.
    """
    site = ctx.obj
    if value is None:
        default = site.paths.sanity_check_folder
        if default is not None and default.exists():
            warning(
                f"sanity check folder not provided, but the "
                f'"{site.name}" site default was found. Using "{default}"'
            )
            _ensure_writable(default)
            return default
        raise click.ClickException(
            f'No sanity check folder specified, and the "{site.name}" site has no '
            "usable default. Please supply --sanity-check-folder."
        )

    if not value.exists():
        raise click.ClickException(f"Sanity check folder {value} does not exist.")
    if not value.is_dir():
        raise click.ClickException(f"{value} is not a directory.")
    _ensure_writable(value)
    return value


def _validate_data_folder(ctx, param, value):
    """Validate or infer the data folder path for the resolved site.

    If not provided, use the resolved site's default if it exists; otherwise
    require the caller to provide an explicit `--data-folder` path.
    """
    site = ctx.obj
    if value is None:
        default = site.paths.data_folder
        if default is not None and default.exists():
            warning(
                f'data folder not provided, but the "{site.name}" site '
                f'default was found. Using "{default}"'
            )
            _ensure_writable(default)
            return default
        raise click.ClickException(
            f'No data folder specified, and the "{site.name}" site has no usable '
            "default. Please supply --data-folder."
        )

    if not value.exists():
        raise click.ClickException(f"Data folder {value} does not exist.")
    if not value.is_dir():
        raise click.ClickException(f"{value} is not a directory.")
    _ensure_writable(value)
    return value


def _is_conda_env(path: Path) -> bool:
    """Whether `path` looks like a conda/mamba environment (vs. a venv)."""
    return (path / "conda-meta").is_dir()


def venv_activate_command(venv_path: Path) -> str:
    """Shell snippet that activates `venv_path`, conda env or venv/virtualenv alike.

    Conda environments are activated via `conda shell.bash hook`, the
    officially-supported way to activate a non-base env in a non-interactive
    shell without depending on `conda init` having modified `~/.bashrc`. This
    requires the `conda` executable to already be on `$PATH` (e.g. via a
    site's `slurm.modules`, or an already-loaded shell environment).
    """
    if _is_conda_env(venv_path):
        return f'eval "$(conda shell.bash hook)"\nconda activate {venv_path}'
    return f"source {venv_path}/bin/activate"


def _validate_venv(ctx, param, value):
    """Validate or infer the path to a Python virtual environment.

    If --venv is provided, verify that it exists and is either a venv/
    virtualenv (contains bin/activate) or a conda/mamba environment (contains
    conda-meta/). If --venv is not provided, try the resolved site's default
    venv and use it with a warning. If the site has no usable default, raise
    a ClickException.
    """
    def_err = "See README.md for installation instruction."
    site = ctx.obj

    if value is None:
        default = site.paths.venv
        if default is not None and default.exists():
            warning(
                f'venv is not provided, but the "{site.name}" site default '
                f'was found. Using "{default}" environment'
            )
            return default
        raise click.ClickException(
            f'No virtual environment specified, and the "{site.name}" site has no '
            "usable default. Please supply --venv path."
        )

    if not value.exists():
        raise click.ClickException(
            f"Python virtual environment directory {value} does not exist. {def_err}"
        )
    if not (_is_conda_env(value) or (value / "bin/activate").exists()):
        raise click.ClickException(
            f"{value} does not seem to be a Python virtual environment or a "
            f"conda environment. {def_err}"
        )
    return value


rdb_link_option = click.option(
    "-r", "--rdb-link", required=True, help="SARAO Archive RDB file link (full url)."
)

dry_run_option = click.option(
    "--dry-run",
    is_flag=True,
    help="Create sbatch scripts (or print local commands) but do not "
    "submit/run them, and exit.",
)

data_folder_option = click.option(
    "-d",
    "--data-folder",
    type=PATH_DW,
    default=None,
    show_default=False,
    callback=_validate_data_folder,
    help=(
        "Directory for storing the extracted data. If not provided, the "
        "resolved site's default (if configured) will be used (a warning "
        "will be emitted)."
    ),
)

sanity_check_folder_option = click.option(
    "--sanity-check-folder",
    type=PATH_DW,
    default=None,
    show_default=False,
    callback=_validate_sanity_check_folder,
    help=(
        "Folder to save sanity check results. If not provided, the resolved "
        "site's default (if configured) will be used (a warning will be "
        "emitted)."
    ),
)

venv_option = click.option(
    "-v",
    "--venv",
    type=click.Path(resolve_path=True, path_type=Path),
    default=None,
    show_default=False,
    callback=_validate_venv,
    help=(
        "Path to the Python virtual environment to use. If not provided, "
        "the resolved site's default (if configured) will be used. Accepts "
        "either a venv/virtualenv (activated via `source {venv}/bin/"
        "activate`) or a conda/mamba environment, detected by the presence "
        "of `conda-meta/` (activated via `conda activate {venv}`)."
    ),
)


def _validate_full_tmp_folder(ctx, param, value):
    """Check write permission for `--full-tmp-folder`, if provided.

    The directory may not exist yet (it gets created later), so check the
    nearest existing ancestor instead.
    """
    if value is None:
        return value
    existing = value
    while not existing.exists():
        existing = existing.parent
    _ensure_writable(existing)
    return value


full_tmp_folder_option = click.option(
    "--full-tmp-folder",
    type=click.Path(resolve_path=True, file_okay=False, path_type=Path),
    default=None,
    show_default=False,
    callback=_validate_full_tmp_folder,
    help=(
        "Directory for storing temporary full raw data during download. "
        "If not provided, defaults to data_folder/full_tmp/cbid. "
        "This directory will be cleaned up after extraction unless "
        "--no-cleanup is specified."
    ),
)

slurm_override_option = click.option(
    "-s",
    "--slurm-override",
    "slurm_override",
    type=str,
    multiple=True,
    help=(
        "Override a SLURM sbatch directive for this run, e.g. "
        '--slurm-override "--mem=64GB". Can be repeated. Applies to every '
        "job step in this invocation uniformly (not per-step); for "
        "per-step tuning, use a custom --site-config instead. Ignored "
        '(with a warning) when the resolved site\'s scheduler is "local".'
    ),
)


def _extract_cbid_and_token_from_rdb_link(rdb_link):
    """Extract CBID and token from RDB link URL."""
    parsed = urllib.parse.urlsplit(rdb_link)
    if parsed.scheme not in ("http", "https"):
        raise click.ClickException("RDB link must be a valid URL starting with http")

    # Extract CBID from URL path (e.g., /1756679237/1756679237_sdp_l0.full.rdb)
    path_parts = [p for p in parsed.path.split("/") if p]
    if not path_parts:
        raise click.ClickException("Invalid RDB link format: cannot extract CBID")
    cbid = path_parts[0]

    # Extract token from query parameter
    query = urllib.parse.parse_qs(parsed.query)
    if "token" not in query:
        raise click.ClickException("RDB link must contain a token parameter")

    token = query["token"][0]

    return cbid, token


def _ensure_job_dirs():
    """Create the ./logs and ./sbatch directories used by generated jobs."""
    Path("./logs").mkdir(parents=True, exist_ok=True)
    Path("./sbatch").mkdir(parents=True, exist_ok=True)
