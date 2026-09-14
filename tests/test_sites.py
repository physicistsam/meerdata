import subprocess
from pathlib import Path

import click
import pytest

from meerdata import sites


def test_list_known_sites_includes_shipped_configs():
    known = sites.list_known_sites()
    assert "ilifu" in known
    assert "local" in known


def test_load_site_config_ilifu():
    site = sites.load_site_config("ilifu")
    assert site.name == "ilifu"
    assert site.scheduler == "slurm"
    assert site.paths.venv == Path("/idia/projects/meerklass/virtualenv/meerklass")
    assert "--account=b205-meerklass-ag" in site.slurm.options
    assert "--partition=Main" in site.slurm.options
    assert "--cpus-per-task=16" in site.slurm.resources["download"]


def test_load_site_config_local():
    site = sites.load_site_config("local")
    assert site.name == "local"
    assert site.scheduler == "local"
    assert site.paths.venv is None
    assert site.paths.data_folder is None


def test_load_site_config_unknown_raises():
    with pytest.raises(click.ClickException):
        sites.load_site_config("does-not-exist")


def test_load_site_config_custom_path(tmp_path):
    custom = tmp_path / "custom_hpc.yaml"
    custom.write_text(
        "scheduler: slurm\n"
        "paths:\n"
        "  venv: /custom/venv\n"
        "slurm:\n"
        "  options:\n"
        "    - --account=my-account\n"
        "    - --partition=batch\n"
    )
    site = sites.load_site_config(str(custom))
    assert site.name == "custom_hpc"
    assert site.scheduler == "slurm"
    assert site.paths.venv == Path("/custom/venv")
    assert "--account=my-account" in site.slurm.options


def test_detect_site_with_markers(monkeypatch):
    monkeypatch.setenv("SLURM_CLUSTER_NAME", "ilifu-slurm2021")

    class DummyRun:
        stdout = "My cluster name is ilifu-slurm2021"
        stderr = ""

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: DummyRun())
    # Isolate this from whatever real filesystem the test happens to run on
    # (e.g. a CHPC login node genuinely has /mnt/lustre/users and
    # /home/apps/chpc, which would otherwise satisfy chpc.yaml's own
    # path_exists markers and win over ilifu since "chpc" sorts first).
    monkeypatch.setattr(sites.Path, "exists", lambda self: False)

    assert sites.detect_site() == "ilifu"


def test_detect_site_negative(monkeypatch):
    monkeypatch.delenv("SLURM_CLUSTER_NAME", raising=False)
    monkeypatch.delenv("SLURM_JOB_ID", raising=False)
    monkeypatch.setattr(sites.socket, "getfqdn", lambda: "myhost.local")

    class DummyRun:
        stdout = ""
        stderr = ""

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: DummyRun())
    monkeypatch.setattr(sites.Path, "exists", lambda self: False)

    assert sites.detect_site() is None


def test_resolve_site_explicit_site_wins(monkeypatch):
    monkeypatch.setenv("MEERDATA_SITE", "ilifu")
    site = sites.resolve_site(explicit_site="local")
    assert site.name == "local"


def test_resolve_site_explicit_config_path_wins(tmp_path):
    custom = tmp_path / "other.yaml"
    custom.write_text("scheduler: local\n")
    site = sites.resolve_site(explicit_site="ilifu", explicit_config_path=str(custom))
    assert site.name == "other"
    assert site.scheduler == "local"


def test_resolve_site_env_var(monkeypatch):
    monkeypatch.setenv("MEERDATA_SITE", "local")
    site = sites.resolve_site()
    assert site.name == "local"


def test_resolve_site_falls_back_to_local(monkeypatch):
    monkeypatch.delenv("MEERDATA_SITE", raising=False)
    monkeypatch.setattr(sites, "detect_site", lambda: None)
    site = sites.resolve_site()
    assert site.name == "local"
