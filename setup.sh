#!/bin/bash

# Ensure that python>=3.6, required for katdal
pytest=$(python -c 'import sys; print(0) if sys.version_info.major >= 3 and sys.version_info.minor >= 6 else print(1)')
if [[ ${pytest} == 1 ]]
then
    echo "Your Python version is less than 3.6, which is required by katdal" 
    exit 1
fi

local_repo_dir=$(dirname "$(realpath "$0")")
echo "Creating a Python venv in ${local_repo_dir}"
virtualenv ${local_repo_dir}/venv/meerdata
source ${local_repo_dir}/venv/meerdata/bin/activate
echo "Python executable is now: $(which python)"
python --version

echo "Upgrading pip"
python -m pip install --upgrade pip

echo "Installing modules."
python -m pip install -r requirements.txt

echo "Making logs directory for storing SLURM log files"
mkdir -P logs sbatch

echo "Set up completed."