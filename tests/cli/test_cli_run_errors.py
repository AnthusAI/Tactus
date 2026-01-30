from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from tactus.cli.app import app

pytestmark = pytest.mark.integration


class FakeValidator:
    def validate(self, content, mode=None):
        return SimpleNamespace(errors=[], warnings=[], registry=None)


@pytest.fixture
def cli_runner():
    return CliRunner()


@pytest.fixture
def minimal_workflow_file(tmp_path):
    path = tmp_path / "minimal.tac"
    path.write_text("return { ok = true }")
    return path


def test_cli_run_rejects_bad_param_format(cli_runner, minimal_workflow_file):
    result = cli_runner.invoke(app, ["run", str(minimal_workflow_file), "--param", "not-a-pair"])
    assert result.exit_code == 1
    assert "expected key=value" in result.stdout.lower()


def test_cli_run_rejects_unknown_storage(cli_runner, minimal_workflow_file, monkeypatch):
    monkeypatch.setattr("tactus.cli.app.TactusValidator", lambda: FakeValidator())
    result = cli_runner.invoke(
        app, ["run", str(minimal_workflow_file), "--storage", "unknown", "--no-sandbox"]
    )
    assert result.exit_code == 1
    assert "unknown storage backend" in result.stdout.lower()


def test_cli_run_requires_docker_when_sandbox_required(
    cli_runner, minimal_workflow_file, monkeypatch
):
    monkeypatch.setattr("tactus.cli.app.TactusValidator", lambda: FakeValidator())

    class FakeConfigManager:
        def load_cascade(self, path):
            return {}

    monkeypatch.setattr("tactus.core.config_manager.ConfigManager", lambda: FakeConfigManager())
    monkeypatch.setattr("tactus.sandbox.is_docker_available", lambda: (False, "missing"))

    result = cli_runner.invoke(app, ["run", str(minimal_workflow_file), "--sandbox"])
    assert result.exit_code == 1
    assert "docker not available" in result.stdout.lower()
