"""Utilities for detecting Ilifu environment and storing Ilifu defaults.

This module provides a combined heuristic to detect whether the code is
running on the Ilifu cluster. The heuristic checks multiple markers so the
check is robust across login shells and batch jobs.
"""

import os
import socket
import subprocess
from pathlib import Path

# Ilifu default paths
VENV_DEFAULT = Path("/idia/projects/meerklass/virtualenv/meerklass")
DATA_FOLDER_DEFAULT = Path("/idia/projects/meerklass/MEERKLASS-1/raw_data")
SANITY_CHECK_FOLDER_DEFAULT = Path(
    "/idia/projects/meerklass/MEERKLASS-1/museek/sanity_checks"
)


def detect_ilifu() -> tuple[bool, dict[str, bool]]:
    """Return (is_ilifu, markers) using multiple heuristics.

    Markers checked:
      - SLURM_CLUSTER_NAME contains 'ilifu'
      - SLURM_JOB_ID is present
      - hostname contains 'ilifu' or endswith '.ilifu.ac.za'
      - presence of /idia/projects
      - presence of /idia/projects/meerklass
      - presence of shared venv path
      - lsid output contains 'ilifu' (if lsid available)

    The function returns True when at least 2 markers are True.
    """
    markers: dict[str, bool] = {}

    markers["slurm_cluster"] = bool(
        os.environ.get("SLURM_CLUSTER_NAME")
        and "ilifu" in os.environ.get("SLURM_CLUSTER_NAME", "").lower()
    )
    markers["slurm_job"] = "SLURM_JOB_ID" in os.environ

    hn = socket.getfqdn().lower()
    markers["hostname"] = ("ilifu" in hn) or hn.endswith(".ilifu.ac.za")

    markers["idia_mount"] = Path("/idia/projects").exists()
    markers["meerklass_project"] = Path("/idia/projects/meerklass").exists()
    markers["shared_venv"] = VENV_DEFAULT.exists()

    # Try to run `lsid` to inspect cluster name when available
    try:
        res = subprocess.run(["lsid"], capture_output=True, text=True, check=False)
        out = (res.stdout or "") + (res.stderr or "")
        markers["lsid"] = "ilifu" in out.lower()
    except Exception:
        markers["lsid"] = False

    score = sum(1 for v in markers.values() if v)
    return score >= 2, markers
