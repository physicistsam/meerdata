# Changelog

All notable changes to the MeerKLASS Data Management Tool will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] - 2026-08-17

### Added
- Pluggable site configuration (`meerdata/configs/*.yaml`, `meerdata/sites.py`): default paths and SLURM settings are now data-driven per site instead of hardcoded for Ilifu. A site's `slurm.options` and `slurm.resources` are lists of raw `--flag=value` sbatch directives, so any SBATCH-compatible option can be set in config, not just a fixed set of fields. Site is resolved via `--site-config`, `--site`, the `MEERDATA_SITE` environment variable, auto-detection (unchanged zero-flag Ilifu experience), or a `local` fallback.
- `local` site: `pull`, `check`, and `extract` run each step directly as a foreground subprocess instead of generating and submitting SLURM sbatch scripts, so the tool now works without any SLURM installation.
- `-s`/`--slurm-override` option on `pull`, `check`, and `extract` to override any generated `#SBATCH` directive for a single run (ignored, with a warning, in local mode).
- `--venv` now also accepts conda/mamba environments (detected by the presence of `conda-meta/`), activated via `conda shell.bash hook` + `conda activate` in generated job bodies instead of `source {venv}/bin/activate`. Requires `conda` to be on `$PATH` in the job's shell.

### Changed
- Moved the `meerdata` package to the standard `src/` layout (`meerdata/` → `src/meerdata/`), matching the sibling `museek` project.
- Split the single `meerdata/cli.py` into a `meerdata/cli/` package (`common.py`, `slurm.py`, and one module per command), consolidating previously-duplicated option declarations and directory-creation logic into `common.py`.
- `check`'s `--context-folder` option (and the underlying `CONTEXT_FOLDER_DEFAULT`/`_validate_context_folder` names) are now `--sanity-check-folder` everywhere, matching `verify`'s equivalent option, which is `--data-folder`. Both now share the same `data_folder_option`/`sanity_check_folder_option` decorators.

### Removed
- `--mail-user`/`--mail-type` options on `pull`, `check`, and `extract`. Mail notifications (and any other SBATCH directive) are now set via a site config's `slurm.options`/`slurm.resources`, or per-run via `-s`/`--slurm-override`.
- `mvftoms_otf_patch.py` and the `--use-patched-mvftoms` option on `pull`/`extract` (deprecated since the previous release). `pull`/`extract` now always use katdal's `mvftoms.py`.
- `meerdata/ilifu.py` (`detect_ilifu()`, `VENV_DEFAULT`, `DATA_FOLDER_DEFAULT`, `SANITY_CHECK_FOLDER_DEFAULT`) — superseded by `meerdata/sites.py` and `meerdata/configs/ilifu.yaml`. This is a breaking change for anyone importing from `meerdata.ilifu` directly.
- `python-casacore`, `katdal`, `katpoint`, and `numpy` from `meerdata`'s own dependencies — they were only needed by `mvftoms_otf_patch.py`.

## [1.1.0] - 2026-01-23

### Added
- `--no-cleanup` option to `pull` to skip the full raw data cleanup step at the end.
- Standardized `--venv` option (default: `/idia/projects/meerklass/virtualenv/meerklass`) for `pull`, `extract`, and `check`. The specified venv is activated in generated sbatch scripts via `source {venv}/bin/activate`.
- Validation for provided `--venv` paths (checks that directory exists and contains `bin/activate`).
- Tests for `--venv` behavior and `--no-cleanup` option.

## [1.0.0] - 2025-12-15

### Added
- Converted repository to installable Python package with `pyproject.toml`
- Package can now be installed with `pip install -e .` or `pip install .`
- Added `meerdata` command as package entry point (alternative to `python meerdata.py`)
- Also install `mvftoms_otf_patch.py` as a command
- Email notification support via `--mail-user` and `--mail-type` options for all commands
- Documentation for email notifications in README

### Changed
- Reorganized code structure:
  - `meerdata.py` → `meerdata/cli.py` (main CLI implementation)
  - `mvftoms-OTF-patch.py` → `meerdata/mvftoms_otf_patch.py` (MVF to MS conversion)
  - Added `meerdata/__init__.py` (package initialization)
- Updated README with installation instructions

### Technical Improvements
- Unified step-based architecture for pull/extract/check commands
- Eliminated ~200+ lines of code duplication through refactoring
- Standardized SLURM script generation with `_create_sbatch_script()`
- Consolidated job submission logic with `_write_and_submit_data_jobs()`

## [Pre-1.0.0] - Historical Development

### Features
- `pull` command: Download data from SARAO archive
- `extract` command: Extract auto/cross-correlations from local RDB files
- `check` command: Run sanity checks on data blocks
- `verify` command: Check disk usage and existence of data blocks
- SLURM job submission and dependency management
- Support for auto-correlations (single dish IM data)
- Support for cross-correlations (OTF measurement sets)
- Automatic cleanup after extraction
