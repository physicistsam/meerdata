import click
import pytest

from meerdata.cli import common
from meerdata.sites import SiteConfig, SitePaths, SlurmConfig


class FakeCtx:
    def __init__(self, site):
        self.obj = site


def _site(name="testsite", **paths):
    return SiteConfig(
        name=name,
        scheduler="slurm",
        paths=SitePaths(**paths),
        slurm=SlurmConfig(),
    )


def test_validate_venv_uses_site_default(tmp_path, capsys):
    venv_dir = tmp_path / "venv"
    venv_dir.mkdir()
    ctx = FakeCtx(_site(venv=venv_dir))

    res = common._validate_venv(ctx, None, None)
    captured = capsys.readouterr()
    assert res == venv_dir
    assert (
        'WARNING: venv is not provided, but the "testsite" site default' in captured.out
    )


def test_validate_venv_missing_default_raises(tmp_path):
    ctx = FakeCtx(_site(venv=tmp_path / "does-not-exist"))
    with pytest.raises(click.ClickException):
        common._validate_venv(ctx, None, None)


def test_validate_venv_no_default_raises():
    ctx = FakeCtx(_site())
    with pytest.raises(click.ClickException):
        common._validate_venv(ctx, None, None)


def test_validate_venv_accepts_conda_env(tmp_path):
    conda_env = tmp_path / "conda_env"
    (conda_env / "conda-meta").mkdir(parents=True)
    ctx = FakeCtx(_site())

    res = common._validate_venv(ctx, None, conda_env)
    assert res == conda_env


def test_validate_venv_rejects_dir_without_activate_or_conda_meta(tmp_path):
    bad = tmp_path / "not-an-env"
    bad.mkdir()
    ctx = FakeCtx(_site())

    with pytest.raises(click.ClickException):
        common._validate_venv(ctx, None, bad)


def test_venv_activate_command_for_venv(tmp_path):
    venv = tmp_path / "venv"
    (venv / "bin").mkdir(parents=True)
    (venv / "bin" / "activate").write_text("# fake activate")

    assert common.venv_activate_command(venv) == f"source {venv}/bin/activate"


def test_venv_activate_command_for_conda_env(tmp_path):
    conda_env = tmp_path / "conda_env"
    (conda_env / "conda-meta").mkdir(parents=True)

    cmd = common.venv_activate_command(conda_env)
    assert cmd == f'eval "$(conda shell.bash hook)"\nconda activate {conda_env}'


def test_validate_data_folder_uses_site_default(tmp_path, capsys):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    ctx = FakeCtx(_site(data_folder=data_dir))

    res = common._validate_data_folder(ctx, None, None)
    captured = capsys.readouterr()
    assert res == data_dir
    assert "WARNING: data folder not provided" in captured.out


def test_validate_data_folder_no_default_raises():
    ctx = FakeCtx(_site())
    with pytest.raises(click.ClickException):
        common._validate_data_folder(ctx, None, None)


def test_validate_sanity_check_folder_uses_site_default(tmp_path, capsys):
    folder = tmp_path / "sanity"
    folder.mkdir()
    ctx = FakeCtx(_site(sanity_check_folder=folder))

    res = common._validate_sanity_check_folder(ctx, None, None)
    captured = capsys.readouterr()
    assert res == folder
    assert "WARNING: sanity check folder not provided" in captured.out


def test_validate_sanity_check_folder_no_default_raises():
    ctx = FakeCtx(_site())
    with pytest.raises(click.ClickException):
        common._validate_sanity_check_folder(ctx, None, None)
