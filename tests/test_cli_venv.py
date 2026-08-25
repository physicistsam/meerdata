import stat
from pathlib import Path

from click.testing import CliRunner

from meerdata.cli import cli

# Force SLURM-mode (sbatch generation) regardless of what machine tests run
# on; without this, site auto-detection would resolve to "local" here and
# skip sbatch generation entirely.
SITE_ARGS = ["--site", "ilifu"]


def make_fake_venv(tmp_path: Path) -> Path:
    venv = tmp_path / "venv_fake"
    bin_dir = venv / "bin"
    bin_dir.mkdir(parents=True)
    activate = bin_dir / "activate"
    activate.write_text("# fake activate")
    # Make it executable just in case
    activate.chmod(activate.stat().st_mode | stat.S_IEXEC)
    return venv


def test_pull_includes_venv_source(tmp_path: Path, monkeypatch):
    runner = CliRunner()
    # Prepare directories
    data_folder = tmp_path / "data"
    data_folder.mkdir()
    venv = make_fake_venv(tmp_path)

    # Use a fake RDB link (parser only extracts CBID and token)
    rdb_link = "https://archive-gw-1.kat.ac.za/1234567890/1234567890_sdp_l0.full.rdb?token=abcd"

    # Run the command in tmp_path so sbatch/logs are created there
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(
        cli,
        [
            *SITE_ARGS,
            "pull",
            "-r",
            rdb_link,
            "--data-folder",
            str(data_folder),
            "--venv",
            str(venv),
            "--dry-run",
        ],
    )

    assert result.exit_code == 0, result.output

    # Find the auto extraction script and assert it contains the source line
    cbid = "1234567890"
    auto_script = tmp_path / "sbatch" / f"local_extract_auto-{cbid}.sbatch"
    assert auto_script.exists(), auto_script

    content = auto_script.read_text()
    assert f"source {venv}/bin/activate" in content

    # Cleanup script should NOT include the venv activation (it runs plain rm)
    cleanup_script = tmp_path / "sbatch" / f"cleanup-{cbid}.sbatch"
    assert cleanup_script.exists(), cleanup_script
    assert f"source {venv}/bin/activate" not in cleanup_script.read_text()


def test_pull_dry_run_prints_sbatch_content(tmp_path: Path, monkeypatch, caplog):
    """--dry-run should print each generated sbatch script's content, not just its path."""
    runner = CliRunner()
    data_folder = tmp_path / "data"
    data_folder.mkdir()
    venv = make_fake_venv(tmp_path)

    rdb_link = (
        "https://archive-gw-1.kat.ac.za/7777777777/7777777777_sdp_l0.full.rdb?token=tok"
    )

    monkeypatch.chdir(tmp_path)

    caplog.set_level("INFO", logger="meerdata")
    result = runner.invoke(
        cli,
        [
            *SITE_ARGS,
            "pull",
            "-r",
            rdb_link,
            "--data-folder",
            str(data_folder),
            "--venv",
            str(venv),
            "--dry-run",
        ],
    )

    assert result.exit_code == 0, result.output

    cbid = "7777777777"
    auto_script = tmp_path / "sbatch" / f"local_extract_auto-{cbid}.sbatch"
    assert auto_script.exists(), auto_script
    content = auto_script.read_text()

    assert "Created sbatch script:" in caplog.text
    assert content in result.output


def test_check_includes_venv_source(tmp_path: Path, monkeypatch):
    runner = CliRunner()
    venv = make_fake_venv(tmp_path)
    context = tmp_path / "context"
    context.mkdir()

    rdb_link = (
        "https://archive-gw-1.kat.ac.za/9876543210/9876543210_sdp_l0.full.rdb?token=tok"
    )

    monkeypatch.chdir(tmp_path)

    result = runner.invoke(
        cli,
        [
            *SITE_ARGS,
            "check",
            "-r",
            rdb_link,
            "--sanity-check-folder",
            str(context),
            "--venv",
            str(venv),
            "--dry-run",
        ],
    )

    assert result.exit_code == 0, result.output

    cbid = "9876543210"
    sanity_script = tmp_path / "sbatch" / f"sanity-check-{cbid}.sbatch"
    assert sanity_script.exists(), sanity_script

    content = sanity_script.read_text()
    assert f"source {venv}/bin/activate" in content


def make_fake_conda_env(tmp_path: Path) -> Path:
    conda_env = tmp_path / "conda_env_fake"
    (conda_env / "conda-meta").mkdir(parents=True)
    return conda_env


def test_pull_includes_conda_activate(tmp_path: Path, monkeypatch):
    runner = CliRunner()
    data_folder = tmp_path / "data"
    data_folder.mkdir()
    conda_env = make_fake_conda_env(tmp_path)

    rdb_link = "https://archive-gw-1.kat.ac.za/1234567891/1234567891_sdp_l0.full.rdb?token=abcd"

    monkeypatch.chdir(tmp_path)

    result = runner.invoke(
        cli,
        [
            *SITE_ARGS,
            "pull",
            "-r",
            rdb_link,
            "--data-folder",
            str(data_folder),
            "--venv",
            str(conda_env),
            "--dry-run",
        ],
    )

    assert result.exit_code == 0, result.output

    cbid = "1234567891"
    auto_script = tmp_path / "sbatch" / f"local_extract_auto-{cbid}.sbatch"
    assert auto_script.exists(), auto_script

    content = auto_script.read_text()
    assert 'eval "$(conda shell.bash hook)"' in content
    assert f"conda activate {conda_env}" in content
    assert f"source {conda_env}/bin/activate" not in content


def test_pull_no_cleanup(tmp_path: Path, monkeypatch):
    """When --no-cleanup is passed the cleanup sbatch should not be created."""
    runner = CliRunner()
    data_folder = tmp_path / "data"
    data_folder.mkdir()
    venv = make_fake_venv(tmp_path)

    rdb_link = (
        "https://archive-gw-1.kat.ac.za/1111111111/1111111111_sdp_l0.full.rdb?token=tok"
    )

    monkeypatch.chdir(tmp_path)

    result = runner.invoke(
        cli,
        [
            *SITE_ARGS,
            "pull",
            "-r",
            rdb_link,
            "--data-folder",
            str(data_folder),
            "--venv",
            str(venv),
            "--no-cleanup",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0, result.output

    cbid = "1111111111"
    cleanup_script = tmp_path / "sbatch" / f"cleanup-{cbid}.sbatch"
    assert not cleanup_script.exists(), (
        "cleanup script should not be created when --no-cleanup is used"
    )


def test_pull_creates_cleanup(tmp_path: Path, monkeypatch):
    """When --no-cleanup is not passed the cleanup sbatch should be created."""
    runner = CliRunner()
    data_folder = tmp_path / "data"
    data_folder.mkdir()
    venv = make_fake_venv(tmp_path)

    rdb_link = (
        "https://archive-gw-1.kat.ac.za/3333333333/3333333333_sdp_l0.full.rdb?token=tok"
    )

    monkeypatch.chdir(tmp_path)

    result = runner.invoke(
        cli,
        [
            *SITE_ARGS,
            "pull",
            "-r",
            rdb_link,
            "--data-folder",
            str(data_folder),
            "--venv",
            str(venv),
            "--dry-run",
        ],
    )

    assert result.exit_code == 0, result.output

    cbid = "3333333333"
    cleanup_script = tmp_path / "sbatch" / f"cleanup-{cbid}.sbatch"
    assert cleanup_script.exists(), (
        "cleanup script should be created when --no-cleanup is not used"
    )


def test_pull_venv_validation_errors(tmp_path: Path, monkeypatch):
    """Pull should fail for non-existent or invalid venv paths."""
    runner = CliRunner()
    data_folder = tmp_path / "data"
    data_folder.mkdir()

    rdb_link = (
        "https://archive-gw-1.kat.ac.za/6666666666/6666666666_sdp_l0.full.rdb?token=tok"
    )

    monkeypatch.chdir(tmp_path)

    # Non-existent venv
    result_missing = runner.invoke(
        cli,
        [
            *SITE_ARGS,
            "pull",
            "-r",
            rdb_link,
            "--data-folder",
            str(data_folder),
            "--venv",
            "/path/does/not/exist",
            "--dry-run",
        ],
    )

    assert result_missing.exit_code != 0
    out_exc = (result_missing.output or "") + (str(result_missing.exception) or "")
    assert "Python virtual environment directory" in out_exc

    # Venv exists but missing activate
    bad_venv = tmp_path / "badvenv"
    (bad_venv / "bin").mkdir(parents=True)

    result_bad = runner.invoke(
        cli,
        [
            *SITE_ARGS,
            "pull",
            "-r",
            rdb_link,
            "--data-folder",
            str(data_folder),
            "--venv",
            str(bad_venv),
            "--dry-run",
        ],
    )

    assert result_bad.exit_code != 0
    out_exc = (result_bad.output or "") + (str(result_bad.exception) or "")
    assert "does not seem to be a Python virtual environment" in out_exc


def test_extract_includes_venv_source(tmp_path: Path, monkeypatch):
    """Ensure extract sbatch scripts include the provided venv activation."""
    runner = CliRunner()
    # Create a fake rdb file
    cbid = "4444444444"
    rdb_file = tmp_path / f"{cbid}_sdp_l0.full.rdb"
    rdb_file.write_text("fake")

    venv = make_fake_venv(tmp_path)
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    monkeypatch.chdir(tmp_path)

    result = runner.invoke(
        cli,
        [
            *SITE_ARGS,
            "extract",
            "--rdb-file",
            str(rdb_file),
            "--data-folder",
            str(tmp_path / "data"),
            "--venv",
            str(venv),
            "--dry-run",
        ],
    )

    assert result.exit_code == 0, result.output

    auto_script = tmp_path / "sbatch" / f"local_extract_auto-{cbid}.sbatch"
    assert auto_script.exists(), auto_script
    assert f"source {venv}/bin/activate" in auto_script.read_text()

    # Cleanup script should NOT include the venv activation (it runs plain rm)
    cleanup_script = tmp_path / "sbatch" / f"cleanup-{cbid}.sbatch"
    assert cleanup_script.exists(), cleanup_script
    assert f"source {venv}/bin/activate" not in cleanup_script.read_text()


def test_extract_venv_validation_errors(tmp_path: Path, monkeypatch):
    """Extract should fail for non-existent or invalid venv paths."""
    runner = CliRunner()
    # Create a fake rdb file
    cbid = "5555555555"
    rdb_file = tmp_path / f"{cbid}_sdp_l0.full.rdb"
    rdb_file.write_text("fake")

    data_dir = tmp_path / "data"
    data_dir.mkdir()

    monkeypatch.chdir(tmp_path)

    # Non-existent venv
    result_missing = runner.invoke(
        cli,
        [
            *SITE_ARGS,
            "extract",
            "--rdb-file",
            str(rdb_file),
            "--data-folder",
            str(tmp_path / "data"),
            "--venv",
            "/does/not/exist",
            "--dry-run",
        ],
    )
    assert result_missing.exit_code != 0
    out_exc = (result_missing.output or "") + (str(result_missing.exception) or "")
    assert "Python virtual environment directory" in out_exc

    # Venv exists but missing activate
    bad_venv = tmp_path / "badvenv"
    (bad_venv / "bin").mkdir(parents=True)

    result_bad = runner.invoke(
        cli,
        [
            *SITE_ARGS,
            "extract",
            "--rdb-file",
            str(rdb_file),
            "--data-folder",
            str(tmp_path / "data"),
            "--venv",
            str(bad_venv),
            "--dry-run",
        ],
    )
    assert result_bad.exit_code != 0
    out_exc = (result_bad.output or "") + (str(result_bad.exception) or "")
    assert "does not seem to be a Python virtual environment" in out_exc


def test_check_venv_validation_errors(tmp_path: Path, monkeypatch):
    """Check should fail fast when the provided --venv is missing or invalid."""
    runner = CliRunner()
    context = tmp_path / "context"
    context.mkdir()

    rdb_link = (
        "https://archive-gw-1.kat.ac.za/2222222222/2222222222_sdp_l0.full.rdb?token=tok"
    )

    monkeypatch.chdir(tmp_path)

    # Non-existent venv path
    result_missing = runner.invoke(
        cli,
        [
            *SITE_ARGS,
            "check",
            "-r",
            rdb_link,
            "--sanity-check-folder",
            str(context),
            "--venv",
            "/path/does/not/exist",
            "--dry-run",
        ],
    )

    assert result_missing.exit_code != 0
    out_exc = (result_missing.output or "") + (str(result_missing.exception) or "")
    assert "Python virtual environment directory" in out_exc

    # Venv exists but missing activate script
    bad_venv = tmp_path / "badvenv"
    (bad_venv / "bin").mkdir(parents=True)

    result_bad = runner.invoke(
        cli,
        [
            *SITE_ARGS,
            "check",
            "-r",
            rdb_link,
            "--sanity-check-folder",
            str(context),
            "--venv",
            str(bad_venv),
            "--dry-run",
        ],
    )

    assert result_bad.exit_code != 0
    out_exc = (result_bad.output or "") + (str(result_bad.exception) or "")
    assert "does not seem to be a Python virtual environment" in out_exc
