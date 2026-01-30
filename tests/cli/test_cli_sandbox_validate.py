from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

import tactus
from tactus.cli.app import app

pytestmark = pytest.mark.integration


@pytest.fixture
def cli_runner():
    return CliRunner()


def test_sandbox_status_reports_availability(monkeypatch, cli_runner):
    class DummyManager:
        full_image_name = "tactus-sandbox:local"

        def image_exists(self):
            return True

        def get_image_version(self):
            return "1.2.3"

    monkeypatch.setattr("tactus.sandbox.is_docker_available", lambda: (True, ""))
    monkeypatch.setattr("tactus.sandbox.DockerManager", DummyManager)

    result = cli_runner.invoke(app, ["sandbox", "status"])

    assert result.exit_code == 0
    assert "Docker Sandbox Status" in result.stdout
    assert "Sandbox image" in result.stdout


def test_sandbox_rebuild_errors_when_docker_unavailable(monkeypatch, cli_runner):
    monkeypatch.setattr("tactus.sandbox.is_docker_available", lambda: (False, "no daemon"))

    result = cli_runner.invoke(app, ["sandbox", "rebuild"])

    assert result.exit_code == 1
    assert "Docker not available" in result.stdout


def test_sandbox_rebuild_errors_when_dockerfile_missing(monkeypatch, tmp_path, cli_runner):
    class DummyManager:
        full_image_name = "tactus-sandbox:local"

        def image_exists(self):
            return False

    monkeypatch.setattr("tactus.sandbox.is_docker_available", lambda: (True, ""))
    monkeypatch.setattr("tactus.sandbox.DockerManager", DummyManager)
    monkeypatch.setattr(
        "tactus.sandbox.docker_manager.resolve_dockerfile_path",
        lambda _path: (tmp_path / "Dockerfile", "source"),
    )

    result = cli_runner.invoke(app, ["sandbox", "rebuild"])

    assert result.exit_code == 1
    assert "Dockerfile not found" in result.stdout


def test_sandbox_rebuild_skips_when_up_to_date(monkeypatch, tmp_path, cli_runner):
    class DummyManager:
        full_image_name = "tactus-sandbox:local"

        def image_exists(self):
            return True

        def get_image_version(self):
            return tactus.__version__

    monkeypatch.setattr("tactus.sandbox.is_docker_available", lambda: (True, ""))
    monkeypatch.setattr("tactus.sandbox.DockerManager", DummyManager)
    dockerfile_path = tmp_path / "Dockerfile"
    dockerfile_path.write_text("FROM scratch\n")
    monkeypatch.setattr(
        "tactus.sandbox.docker_manager.resolve_dockerfile_path",
        lambda _path: (dockerfile_path, "source"),
    )

    result = cli_runner.invoke(app, ["sandbox", "rebuild"])

    assert result.exit_code == 0
    assert "Image is up to date" in result.stdout


def test_validate_lua_reports_warnings(monkeypatch, tmp_path, cli_runner):
    file_path = tmp_path / "workflow.tac"
    file_path.write_text("name('demo')")

    registry = SimpleNamespace(
        description="demo",
        agents={"agent": SimpleNamespace(system_prompt="hi", provider="openai", model="gpt")},
        output_schema={},
        input_schema={},
    )
    result = SimpleNamespace(
        valid=True,
        warnings=[SimpleNamespace(message="watch out")],
        errors=[],
        registry=registry,
    )

    class DummyValidator:
        def validate(self, _text, _mode):
            return result

    monkeypatch.setattr("tactus.cli.app.TactusValidator", DummyValidator)

    response = cli_runner.invoke(app, ["validate", str(file_path)])

    assert response.exit_code == 0
    assert "DSL is valid" in response.stdout
    assert "Warning" in response.stdout
