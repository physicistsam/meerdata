"""
MeerKLASS data management tool.

A command-line tool for MeerKLASS data management including downloading data
from SARAO archive, running sanity checks, extracting correlation data,
and verifying data blocks.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("meerdata")
except PackageNotFoundError:
    __version__ = "unknown"

__author__ = "MeerKLASS Team"

from meerdata.cli import cli

__all__ = ["__version__", "cli"]
