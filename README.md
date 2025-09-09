# MeerKLASS Data Management Tool

A command-line tool for MeerKLASS data management. It provides functionality for downloading the data and running sanity check on the data blocks, as well as checking the disk usage of downloaded data.

## Naming
meerdata (/meːrˈdɑːtə/): 

A make up word from Afrikaans word "meer" meaning "more" and an English word data. More data!

## Requirements

* Access to [SARAO archive](https://archive.sarao.ac.za/)
* Access to ilifu although this tool can technically be run on any cluster with a SLURM job scheduler
* Python >= 3.6
* katdal and other dependencies (installed via `setup.sh`)

## Set Up

1. Clone this repository
2. On illifu, start an interactive shell session: `sinteractive`
3. Run the setup script: `bash setup.sh`
   * This creates a Python virtual environment in `./venv/meerdata/`
   * Installs all required dependencies including katdal, ivory and museek
   * Creates a `logs/` directory for SLURM output files
4. You can then close the interactive shell

## Obtaining RDB link

To access recent MeerKLASS data, you will need a permission from our PI.

A link to the raw `.rdb` file containing the metadata of the data block is required to run sanity check or download it. The RDB link can be obtained by clicking on "COPY RDB LINK" (now ".RDB FILE LINK" after their recent update) on the top right corner.
![SARAO Archive interface showing RDB link ](https://archive.sarao.ac.za/block-annotated.webp)

## Activate Python environment

To use this tool, activate the meerdata Python environment installed by the `setup.sh` script.
```bash
source venv/meerdata/bin/activate
```

Any other Python environment with modules listed in the `requirements.txt` can also be used.

## Usage


The `meerdata.py` script provides three main commands:


### Pull Command - Download Data

```bash
python meerdata.py pull -r "RDB_LINK"
```

**Options:**

* `-r, --rdb-link`: SARAO Archive RDB file link (required)
* `-c, --correlation`: Type of data to pull (default: auto)
  * `auto`: autocorrelations only, i.e. single dish IM data
  * `cross`: cross-correlations (measurement set), i.e. OTF data
  * `all`: both autocorrelations and cross-correlations
* `--data-folder`: Directory for storing data (default: `/idia/projects/meerklass/MEERKLASS-1/uhf_data/XLP2025/raw`)

**Examples:**

```bash
# Download autocorrelations only (default)
python meerdata.py pull -r "https://archive-gw-1.kat.ac.za/1234567890/1234567890_sdp_l0.full.rdb?token=abc123"

# Download cross-correlations only
python meerdata.py pull -r "RDB_LINK" -c cross

# Download both auto and cross correlations
python meerdata.py pull -r "RDB_LINK" -c all

# Specify custom data folder
python meerdata.py pull -r "RDB_LINK" --data-folder /path/to/custom/folder
```

Note that we keep the data folders organised on ilifu. There should be no need to change --data-folder option if you are downloading the lastest campaign (XLP).


### Check Command - Run Sanity Checks

```bash
python meerdata.py check -r "RDB_LINK"
```

**Options:**

* `-r, --rdb-link`: SARAO Archive RDB file link (required)
* `--context-folder`: Directory to save sanity check results (default: `/idia/projects/meerklass/MEERKLASS-1/uhf_data/XLP2025/sanity_checks`)
* `--venv-path`: Path to Python virtual environment (default: `./venv/meerdata`)

**Example:**

```bash
python meerdata.py check -r "https://archive-gw-1.kat.ac.za/1234567890/1234567890_sdp_l0.full.rdb?token=abc123"
```

The sanity check should take about 5 minutes to run. Otherwise, there is likely a networking issue, which can happen from time to time. Simply resubmit the job on the same block.

Once ran, the "formatted output" should be copy to the MeerKLASS data tracking spread sheet.

### Verify Command - Check Disk Usage and Existent of Data Blocks

```bash
python meerdata.py verify -b BLOCK_NUMBER [ -b BLOCK_NUMBER ... ]
```

**Options:**

* `-b, --block-number`: Block number(s) to verify (required, can be specified multiple times)
* `--context-folder`: Directory containing block directories (default: `/idia/projects/meerklass/MEERKLASS-1/uhf_data/XLP2025/raw`)

**Example:**

```bash
python meerdata.py verify -b 1753129121 -b 1753219043 -b 1753297658
```

For each block number, this command will:

* Check if the directory `<context-folder>/<block-number>` exists
* If it exists, report the disk usage in GB
* If the directory exists but is empty (0 GB), print a `[WARNING]`
* If the directory does not exist, print `[MISSING]`
* Print a summary table at the end

## How It Works

### Pull Command

1. Extracts CBID (block number) and token from the RDB link
2. Creates necessary directories
3. Generate and submits SLURM jobs for:
   * Downloading MVF data from SARAO archive
   * Extracting autocorrelations (if requested)
   * Extracting measurement set for cross-correlations (if requested)
   * Cleaning up the MVF files after extraction

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

## Help

For detailed help on any command:

```bash
python meerdata.py --help
python meerdata.py pull --help
python meerdata.py check --help
```
