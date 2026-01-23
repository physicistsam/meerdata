# Changelog

All notable changes to the MeerKLASS Data Management Tool will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] - 2026-01-23

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
