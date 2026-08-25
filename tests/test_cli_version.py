from click.testing import CliRunner

from meerdata.cli import cli


def test_version_option():
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "meerdata, version" in result.output
