"""
MeerKLASS data management tool.

A command-line tool for MeerKLASS data management including downloading data
from SARAO archive, running sanity checks, extracting correlation data,
and verifying data blocks.
"""

__version__ = "0.1.0"
__author__ = "MeerKLASS Team"

from meerdata.cli import cli

__all__ = ["cli", "__version__"]
