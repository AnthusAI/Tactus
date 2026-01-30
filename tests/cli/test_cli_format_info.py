import pytest
from typer.testing import CliRunner

from tactus.cli.app import app

pytestmark = pytest.mark.integration


@pytest.fixture
def cli_runner():
    return CliRunner()


def test_format_stdout(cli_runner, tmp_path):
    file_path = tmp_path / "format.tac"
    file_path.write_text("return {ok=true}")

    result = cli_runner.invoke(app, ["format", str(file_path), "--stdout"])

    assert result.exit_code == 0
    assert "return" in result.stdout


def test_format_check_reports_changes(cli_runner, tmp_path):
    file_path = tmp_path / "format_check.tac"
    file_path.write_text("return {ok=true}")

    result = cli_runner.invoke(app, ["format", str(file_path), "--check"])

    assert result.exit_code == 1
    assert "Would reformat" in result.stdout


def test_info_invalid_file(cli_runner, tmp_path):
    file_path = tmp_path / "invalid.tac"
    file_path.write_text("not lua")

    result = cli_runner.invoke(app, ["info", str(file_path)])

    assert result.exit_code == 1
    assert "Invalid procedure" in result.stdout


def test_format_rejects_wrong_extension(cli_runner, tmp_path):
    file_path = tmp_path / "file.txt"
    file_path.write_text("nope")

    result = cli_runner.invoke(app, ["format", str(file_path)])

    assert result.exit_code == 1
    assert "supported" in result.stdout.lower()
