# MeerKLASS Data Management Tool

A command-line tool for MeerKLASS data management. It provides functionality for downloading the data and running sanity check on the data blocks, as well as checking the disk usage of downloaded data.

## Naming
meerdata (/meːrˈdɑːtə/): 

A make up word from Afrikaans word "meer" meaning "more" and an English word data. More data!

## Requirements

* Access to [SARAO archive](https://archive.sarao.ac.za/). See [Obataining RDB Link.](#obtaining-rdb-link)
* Python >= 3.12
* `pip` (museek and other dependencies are installed automatically when installing this package with `pip`)

## Installation

### Option 1: Pre-installed environment on ilifu

No installation required! Simply activate meerklass shared Python virtual environment.

```
source /idia/projects/meerklass/virtualenv/meerklass/bin/activate
```

Contact @piyanatk if there is any issue with the shared environment

### Option 2: Install from GitHub

> **Note:** This repository is **private**. You must have been granted access to the `meerklass/meerdata` GitHub repository to install directly from GitHub. If you do not have access, contact the project maintainers (e.g., `@piyanatk`) to request repository access.

**Recommended (SSH):** Add your SSH key to your GitHub account following [GitHub's instruction](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/adding-a-new-ssh-key-to-your-github-account) and then install via SSH

```bash
pip install git+ssh://git@github.com/meerklass/meerdata.git
```

or clone via SSH and install locally

```bash
git clone git@github.com:meerklass/meerdata.git
cd meerdata
pip install .
```

**HTTPS with Personal Access Token (if you do not have SSH access):**

```bash
pip install git+https://<USERNAME>:<TOKEN>@github.com/meerklass/meerdata.git
```

*Security tip:* avoid exposing tokens in shell history — prefer using a git credential helper or clone the repo locally and run `pip install .` instead.

### Troubleshoot Compiler Issues

If you run into compiler issues when `pip` tries to install `python-casacore`, you may have to pass explict environment variables for C/C++ compilers and turn off pip cache

```
export CC=gcc
export CXX=g++
export CCACHE_DISABLE=1
pip install git+ssh://git@github.com/meerklass/meerdata.git
```

### Install in development mode

If you want to contribute to meerdata codes, install in editable mode with test dependencies

```
pip install -e .[test]
```

## Usage

After installation, the `meerdata` command will be available:

```bash
meerdata --help
```

The tool provides four main commands: `pull`, `extract`, `check`, and `verify`.

## Site Configuration

`meerdata` needs to know where it's running: default data/venv/sanity-check-folder paths, and whether to submit jobs to SLURM or run them directly (local mode). This is called the "site", and is resolved once per invocation using the first of:

1. `--site-config PATH` — a custom site config YAML file, for HPC systems not shipped with the package.
2. `--site NAME` — an explicit, shipped site name (currently `ilifu` or `local`).
3. The `MEERDATA_SITE` environment variable, set to a shipped site name.
4. Auto-detection — the same "just works on Ilifu" experience as before, using multiple markers (SLURM cluster name, hostname, known mount points) to recognize Ilifu without any flags.
5. Falling back to `local` if nothing above matched — no SLURM, no default paths, so `--data-folder`/`--venv`/`--sanity-check-folder` must be supplied explicitly.

```bash
# Default: auto-detects Ilifu, unchanged zero-flag behavior
meerdata pull -r "RDB_LINK"

# Force a specific known site
meerdata --site local pull -r "RDB_LINK" --data-folder ./data --venv ./venv

# Same, via environment variable (handy for a shell profile / job script)
MEERDATA_SITE=local meerdata pull -r "RDB_LINK" --data-folder ./data --venv ./venv

# Point at a custom site config for an HPC not shipped with the package
meerdata --site-config /path/to/my_cluster.yaml pull -r "RDB_LINK"
```

In `local` mode, `pull`/`check`/`extract` run each processing step (download, extraction, sanity check, cleanup) directly as a foreground subprocess instead of generating and submitting `.sbatch` scripts — no SLURM installation is required.

A SLURM site's config (see [`meerdata/configs/ilifu.yaml`](src/meerdata/configs/ilifu.yaml) for a full example) sets `paths:` and a `slurm:` block. `slurm.options` and each entry in `slurm.resources` are lists of raw `--flag=value` sbatch directives — any SBATCH-compatible option is allowed, not just a fixed set of fields:

```yaml
slurm:
  modules: ["rclone"]           # `module load` lines for the download step
  scontrol_path: "scontrol"     # used to requeue a failed download
  options:                      # applied to every generated job
    - "--account=my-account"
    - "--partition=batch"
  resources:                    # per-step options, override `options` above
    download:
      - "--cpus-per-task=16"
      - "--mem=16GB"
      - "--time=10:00:00"
    # ... auto, ms, cleanup, sanity-check
```

### Pull Command - Download Data

```bash
meerdata pull -r "RDB_LINK"
```

**Options:**

* `-r, --rdb-link`: SARAO Archive RDB file link (required)
* `-c, --correlation`: Type of data to pull (default: auto)
  * `auto`: autocorrelations only, i.e. single dish IM data
  * `cross`: cross-correlations (measurement set), i.e. OTF data
  * `all`: both autocorrelations and cross-correlations
* `--data-folder`: Directory for storing data (no default). If not provided, the resolved site's default (if configured) will be used when available (a warning will be emitted). See [Site Configuration](#site-configuration).
* `--venv`: Path to a Python virtual environment or conda/mamba environment to use (no default). If not provided, the resolved site's default (if configured) will be used when available (a warning will be emitted). A venv/virtualenv is activated via `source {venv}/bin/activate`; a conda/mamba environment (detected by the presence of `conda-meta/`) is activated via `conda activate {venv}` instead — this requires the `conda` executable to be on `$PATH` in the job's shell (e.g. via a site's `slurm.modules`, or an already-loaded shell environment).
* `--no-cleanup`: Skip the full raw data cleanup step at the end (useful for debugging or preserving raw files).
* `-s, --slurm-override`: Override a SLURM sbatch directive for this run, e.g. `--slurm-override "--mem=64GB"`. Can be repeated. Ignored (with a warning) in local mode.

**Examples:**

```bash
# Download autocorrelations only (default)
meerdata pull -r "https://archive-gw-1.kat.ac.za/1234567890/1234567890_sdp_l0.full.rdb?token=abc123"

# Download cross-correlations only
meerdata pull -r "RDB_LINK" -c cross

# Download both auto and cross correlations
meerdata pull -r "RDB_LINK" -c all

# Specify custom data folder
meerdata pull -r "RDB_LINK" --data-folder /path/to/custom/folder

# Skip the final cleanup step (keep raw files)
meerdata pull -r "RDB_LINK" --no-cleanup

# Use a specific Python virtual environment for job scripts
meerdata pull -r "RDB_LINK" --venv /path/to/venv

# Omitting `--venv` will attempt to use the resolved site's default (if configured) when available (a warning will be emitted).

# Override a SLURM resource request for this run only
meerdata pull -r "RDB_LINK" -s "--mem=64GB" -s "--time=02:00:00"
```

Note that we keep the data folders organised on ilifu. There should be no need to change --data-folder option if you are downloading the lastest campaign (XLP).


### Extract Command - Process Local Data

Extract auto or cross-correlation data from local RDB files that have already been downloaded.

```bash
meerdata extract --rdb-file "PATH_TO_LOCAL_RDB"
```

**Options:**

* `--rdb-file`: Path to local RDB file on disk (required)
* `-c, --correlation`: Type of data to extract (default: auto)
  * `auto`: autocorrelations only, i.e. single dish IM data
  * `cross`: cross-correlations (measurement set), i.e. OTF data
  * `all`: both autocorrelations and cross-correlations
* `--data-folder`: Directory for storing extracted data (no default). If not provided, the resolved site's default (if configured) will be used when available (a warning will be emitted).
* `--venv`: Path to a Python virtual environment or conda/mamba environment to use (no default). If not provided, the resolved site's default (if configured) will be used when available (a warning will be emitted). A venv/virtualenv is activated via `source {venv}/bin/activate`; a conda/mamba environment (detected by the presence of `conda-meta/`) is activated via `conda activate {venv}` instead.
* `-s, --slurm-override`: Override a SLURM sbatch directive for this run. Can be repeated. Ignored (with a warning) in local mode.

**Examples:**

```bash
# Extract autocorrelations from local RDB file (default)
meerdata extract --rdb-file /path/to/1234567890_sdp_l0.full.rdb

# Extract cross-correlations only
meerdata extract --rdb-file /path/to/1234567890_sdp_l0.full.rdb -c cross

# Extract both auto and cross correlations
meerdata extract --rdb-file /path/to/1234567890_sdp_l0.full.rdb -c all

# Specify custom data folder
meerdata extract --rdb-file /path/to/1234567890_sdp_l0.full.rdb --data-folder /path/to/custom/folder
```

This command is useful when you have already downloaded the full MVF data locally and want to extract specific correlation types without re-downloading from the archive.


### Check Command - Run Sanity Checks

```bash
meerdata check -r "RDB_LINK"
```

**Options:**

* `-r, --rdb-link`: SARAO Archive RDB file link (required)
* `--sanity-check-folder`: Folder to save sanity check results (no default). If not provided, the resolved site's default (if configured) will be used when available (a warning will be emitted).
* `--venv`: Path to a Python virtual environment or conda/mamba environment (no default). If not provided, the resolved site's default (if configured) will be used when available (a warning will be emitted). A venv/virtualenv is activated via `source {venv}/bin/activate`; a conda/mamba environment (detected by the presence of `conda-meta/`) is activated via `conda activate {venv}` instead.
* `-s, --slurm-override`: Override a SLURM sbatch directive for this run. Can be repeated. Ignored (with a warning) in local mode.

**Example:**

```bash
meerdata check -r "https://archive-gw-1.kat.ac.za/1234567890/1234567890_sdp_l0.full.rdb?token=abc123"
```

The sanity check should take about 5 minutes to run. Otherwise, there is likely a networking issue, which can happen from time to time. Simply resubmit the job on the same block.

Once ran, the "formatted output" should be copy to the MeerKLASS data tracking spread sheet.

### Verify Command - Check Disk Usage and Existent of Data Blocks

```bash
meerdata verify -b BLOCK_NUMBER [ -b BLOCK_NUMBER ... ]
```

**Options:**

* `-b, --block-number`: Block number(s) to verify (required, can be specified multiple times)
* `--data-folder`: Directory containing block directories (no default). If not provided, the resolved site's default (if configured) will be used when available (a warning will be emitted).

**Example:**

```bash
meerdata verify -b 1753129121 -b 1753219043 -b 1753297658
```

For each block number, this command will:

* Check if the directory `<data-folder>/<block-number>` exists
* If it exists, report the disk usage in GB
* If the directory exists but is empty (0 GB), print a `[WARNING]`
* If the directory does not exist, print `[MISSING]`
* Print a summary table at the end


## Obtaining RDB link

To access recent MeerKLASS data, you will need a permission from our PI.

A link to the raw `.rdb` file containing the metadata of the data block is required to run sanity check or download it. The RDB link can be obtained by clicking on "COPY RDB LINK" (now ".RDB FILE LINK" after their recent update) on the top right corner.
![SARAO Archive interface showing RDB link ](https://archive.sarao.ac.za/block-annotated.webp)

## How It Works

### Pull Command

1. Extracts CBID (block number) and token from the RDB link
2. Creates necessary directories
3. Runs (on SLURM sites, generates and submits sbatch jobs for; on `local`, runs directly) each requested step:
   * Downloading MVF data from SARAO archive using `mvf_download.py` script from `katdal`
   * Extracting autocorrelations (if requested) using `mvf_copy.py` script from `katdal`
   * Extracting measurement set for cross-correlations (if requested) using `mvftoms.py` from katdal
   * Cleaning up the MVF files after extraction. This cleanup step can be skipped by passing `--no-cleanup` to `pull` (useful for debugging or preserving raw data)

### Extract Command

1. Infers CBID from the local RDB file name
2. Creates necessary output directories
3. Runs (on SLURM sites, generates and submits sbatch jobs for; on `local`, runs directly):
   * Extracting autocorrelations from local MVF data (if requested)
   * Extracting measurement set for cross-correlations (if requested)
   * Cleaning up temporary files after extraction

### Check Command

1. Extracts CBID and token from the RDB link
2. Runs the museek sanity check plugin (as a submitted SLURM job on SLURM sites, or directly on `local`)
3. Results are saved to the specified sanity check folder

## SLURM Job Management

On sites with `scheduler: slurm` (e.g. Ilifu), the tool automatically generates and submits SBATCH scripts:

* SBATCH scripts, log files, and job titles are attached with the block number for easy tracking
* The generated scripts handle job dependencies:
  * Extraction jobs wait for download to complete
  * Cleanup runs after all extraction jobs finish
  * The download step can be requeued automatically on failure
* `-s`/`--slurm-override` can override any generated `#SBATCH` directive for a single run (see [Site Configuration](#site-configuration) and each command's options above)

All SLURM output logs are saved in the `logs/` directory with descriptive filenames.

On `scheduler: local` sites, none of the above applies — steps run directly as foreground subprocesses, and `-s`/`--slurm-override` is ignored (with a warning).

## Email Notifications

There are no dedicated `--mail-user`/`--mail-type` flags. Instead, since site configs and `-s`/`--slurm-override` accept any SBATCH-compatible option (see [Site Configuration](#site-configuration)), set mail notifications either per-site (in `options:`, so every job at that site gets them) or per-run:

```bash
# Per-run, for this command only
meerdata pull -r "RDB_LINK" -s "--mail-user=user@example.com" -s "--mail-type=ALL"
```

```yaml
# Per-site default, in a site config's slurm: block
slurm:
  options:
    - "--account=..."
    - "--mail-user=team@example.com"
    - "--mail-type=FAIL"
```

See [SLURM sbatch documentation](https://slurm.schedmd.com/sbatch.html) for all `--mail-type` values.

## Help

For detailed help on any command:

```bash
meerdata --help
meerdata pull --help
meerdata extract --help
meerdata check --help
meerdata verify --help
```
