# MeerKLASS Data Management Tool

A command-line tool for MeerKLASS data management. It provides functionality for downloading the data and running sanity check on the data blocks, as well as checking the disk usage of downloaded data.

## Naming
meerdata (/meːrˈdɑːtə/): 

A make up word from Afrikaans word "meer" meaning "more" and an English word data. More data!

## Requirements

* Access to [SARAO archive](https://archive.sarao.ac.za/). See [Obataining RDB Link.](#obtaining-rdb-link)
* Python >= 3.12
* `pip` (katdal, museek and other dependencies are installed automatically when installing this package with `pip`)

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


### Pull Command - Download Data

```bash
meerdata pull -r "RDB_LINK"
# or: python meerdata.py pull -r "RDB_LINK"
```

**Options:**

* `-r, --rdb-link`: SARAO Archive RDB file link (required)
* `-c, --correlation`: Type of data to pull (default: auto)
  * `auto`: autocorrelations only, i.e. single dish IM data
  * `cross`: cross-correlations (measurement set), i.e. OTF data
  * `all`: both autocorrelations and cross-correlations
* `--data-folder`: Directory for storing data (no default). If not provided, the Ilifu default (`/idia/projects/meerklass/MEERKLASS-1/uhf_data/XLP2025/raw`) will be used when available (a warning will be emitted).
* `--venv`: Path to Python virtual environment to use (no default). If not provided, the Ilifu default (`/idia/projects/meerklass/virtualenv/meerklass`) will be used when available (a warning will be emitted). The specified venv will be activated in generated sbatch scripts via `source {venv}/bin/activate`.
* `--no-cleanup`: Skip the full raw data cleanup step at the end (useful for debugging or preserving raw files).

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

# Omitting `--venv` will attempt to use the Ilifu default (`/idia/projects/meerklass/virtualenv/meerklass`) if available (a warning will be emitted).
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
* `--data-folder`: Directory for storing extracted data (no default). If not provided, the Ilifu default (`/idia/projects/meerklass/MEERKLASS-1/uhf_data/XLP2025/raw`) will be used when available (a warning will be emitted).
* `--venv`: Path to Python virtual environment to use (no default). If not provided, the Ilifu default (`/idia/projects/meerklass/virtualenv/meerklass`) will be used when available (a warning will be emitted). The specified venv will be activated in generated sbatch scripts via `source {venv}/bin/activate`. 

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
* `--context-folder`: Directory to save sanity check results (no default). If not provided, the Ilifu default (`/idia/projects/meerklass/MEERKLASS-1/uhf_data/XLP2025/sanity_checks`) will be used when available (a warning will be emitted).
* `--venv`: Path to Python virtual environment (no default). If not provided, the Ilifu default (`/idia/projects/meerklass/virtualenv/meerklass`) will be used when available (a warning will be emitted). The specified venv will be validated and activated in the generated sbatch script via `source {venv}/bin/activate`.

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
* `--context-folder`: Directory containing block directories (no default). If not provided, the Ilifu default (`/idia/projects/meerklass/MEERKLASS-1/uhf_data/XLP2025/raw`) will be used when available (a warning will be emitted).

**Example:**

```bash
meerdata verify -b 1753129121 -b 1753219043 -b 1753297658
```

For each block number, this command will:

* Check if the directory `<context-folder>/<block-number>` exists
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
3. Generate and submits SLURM jobs for:
   * Downloading MVF data from SARAO archive using `mvf_download.py` script from `katdal`
   * Extracting autocorrelations (if requested) using `mvf_copy.py` script from `katdal`
   * Extracting measurement set for cross-correlations (if requested) the `mvftoms.py` from katdal (optionally use the local patched version `mvftoms_otf_patch.py` by passsing `--use-patched-mvftoms`)
   * Cleaning up the MVF files after extraction. This cleanup step can be skipped by passing `--no-cleanup` to `pull` (useful for debugging or preserving raw data)

### Extract Command

1. Infers CBID from the local RDB file name
2. Creates necessary output directories
3. Generates and submits SLURM jobs for:
   * Extracting autocorrelations from local MVF data (if requested)
   * Extracting measurement set for cross-correlations (if requested)
   * Cleaning up temporary files after extraction

### Check Command

1. Extracts CBID and token from the RDB link
2. Generates and submits a SLURM job that runs the museek sanity check plugin
3. Results are saved to the specified context folder

## SLURM Job Management

* The tool automatically generate and submit SBATCH scripts.
* SBATCH scripts, log files, and job titles are attached with the block number for easy tracking
* The generated scripts handle job dependencies:
  * Extraction jobs wait for download to complete
  * Cleanup runs after all extraction jobs finish
  * Failed jobs can be requeued automatically

All SLURM output logs are saved in the `logs/` directory with descriptive filenames.

## Email Notifications

All commands support SLURM email notifications:

* `--mail-user`: Email address to receive notifications
* `--mail-type`: When to send emails (e.g., `BEGIN`, `END`, `FAIL`, `ALL`)

**Example:**

```bash
meerdata pull -r "RDB_LINK" --mail-user user@example.com --mail-type ALL
```

See [SLURM sbatch documentation](https://slurm.schedmd.com/sbatch.html) for more mail type options.

## Help

For detailed help on any command:

```bash
meerdata --help
meerdata pull --help
meerdata extract --help
meerdata check --help
meerdata verify --help
```
