import importlib

import click
import pytest

cli = importlib.import_module("meerdata.cli")


def test_validate_venv_uses_ilifu_default(monkeypatch, capsys):
    # Make detect_ilifu return True
    monkeypatch.setattr(cli, "detect_ilifu", lambda: (True, {"dummy": True}))

    # Substitute VENV_DEFAULT with object that reports exists()
    class D:
        def exists(self):
            return True

    monkeypatch.setattr(cli, "VENV_DEFAULT", D())

    # Should return the default and print a warning
    res = cli._validate_venv(None, None, None)
    captured = capsys.readouterr()
    assert str(res) == str(cli.VENV_DEFAULT)
    assert "WARNING: venv is not provided" in captured.out


def test_validate_venv_missing_default_raises(monkeypatch):
    monkeypatch.setattr(cli, "detect_ilifu", lambda: (True, {"dummy": True}))

    class D:
        def exists(self):
            return False

    monkeypatch.setattr(cli, "VENV_DEFAULT", D())

    with pytest.raises(click.ClickException):
        cli._validate_venv(None, None, None)


def test_validate_data_folder_ilifu_default(monkeypatch, capsys):
    monkeypatch.setattr(cli, "detect_ilifu", lambda: (True, {"dummy": True}))

    class D:
        def exists(self):
            return True

        def is_dir(self):
            return True

    monkeypatch.setattr(cli, "DATA_FOLDER_DEFAULT", D())

    res = cli._validate_data_folder(None, None, None)
    captured = capsys.readouterr()
    assert str(res) == str(cli.DATA_FOLDER_DEFAULT)
    assert "WARNING: data folder not provided" in captured.out


def test_validate_context_folder_ilifu_default(monkeypatch, capsys):
    monkeypatch.setattr(cli, "detect_ilifu", lambda: (True, {"dummy": True}))

    class D:
        def exists(self):
            return True

        def is_dir(self):
            return True

    monkeypatch.setattr(cli, "CONTEXT_FOLDER_DEFAULT", D())

    res = cli._validate_context_folder(None, None, None)
    captured = capsys.readouterr()
    assert str(res) == str(cli.CONTEXT_FOLDER_DEFAULT)
    assert "WARNING: context folder not provided" in captured.out


def test_validate_data_folder_not_ilifu_raises(monkeypatch):
    monkeypatch.setattr(cli, "detect_ilifu", lambda: (False, {}))
    with pytest.raises(click.ClickException):
        cli._validate_data_folder(None, None, None)
