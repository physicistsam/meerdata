import subprocess

import meerdata.ilifu as ilifu


def test_detect_ilifu_with_markers(monkeypatch):
    # Simulate SLURM env and lsid output
    monkeypatch.setenv("SLURM_CLUSTER_NAME", "ilifu-slurm2021")

    class DummyRun:
        stdout = "My cluster name is ilifu-slurm2021"
        stderr = ""

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: DummyRun())

    is_ilifu, markers = ilifu.detect_ilifu()
    assert is_ilifu
    assert markers["lsid"] is True
    assert markers["slurm_cluster"] is True


def test_detect_ilifu_negative(monkeypatch):
    # No markers
    monkeypatch.delenv("SLURM_CLUSTER_NAME", raising=False)
    monkeypatch.delenv("SLURM_JOB_ID", raising=False)

    class DummyRun:
        stdout = ""
        stderr = ""

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: DummyRun())

    # Ensure mount checks fail by pointing defaults to a non-existent temp path
    monkeypatch.setattr(
        ilifu, "VENV_DEFAULT", type("X", (), {"exists": lambda self=None: False})()
    )
    monkeypatch.setattr(
        ilifu,
        "DATA_FOLDER_DEFAULT",
        type("X", (), {"exists": lambda self=None: False})(),
    )
    monkeypatch.setattr(
        ilifu,
        "CONTEXT_FOLDER_DEFAULT",
        type("X", (), {"exists": lambda self=None: False})(),
    )

    # Also make generic Path.exists return False to avoid accidental true markers
    monkeypatch.setattr(ilifu.Path, "exists", lambda self: False)

    is_ilifu, markers = ilifu.detect_ilifu()
    assert not is_ilifu
