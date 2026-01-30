import pytest
import typer

from tactus.cli import app as cli_app


class DummyConsole:
    def __init__(self):
        self.lines = []

    def print(self, *args, **kwargs):
        self.lines.append(" ".join(str(a) for a in args))


class FakeManager:
    def __init__(self, image_exists=True, version="dev", build_result=(True, "ok")):
        self._exists = image_exists
        self._version = version
        self._build_result = build_result
        self.full_image_name = "tactus-sandbox:test"
        self.build_called = False

    def image_exists(self):
        return self._exists

    def get_image_version(self):
        return self._version

    def build_image(self, dockerfile_path, context_path, version, verbose):
        self.build_called = True
        return self._build_result


def test_sandbox_status_reports(monkeypatch):
    console = DummyConsole()
    monkeypatch.setattr(cli_app, "console", console)

    monkeypatch.setattr("tactus.sandbox.is_docker_available", lambda: (True, ""))
    monkeypatch.setattr("tactus.sandbox.DockerManager", lambda: FakeManager(image_exists=True))

    cli_app.sandbox_status()
    assert any("Docker Sandbox Status" in line for line in console.lines)


def test_sandbox_status_no_image(monkeypatch):
    console = DummyConsole()
    monkeypatch.setattr(cli_app, "console", console)

    monkeypatch.setattr("tactus.sandbox.is_docker_available", lambda: (False, "missing"))
    monkeypatch.setattr("tactus.sandbox.DockerManager", lambda: FakeManager(image_exists=False))

    cli_app.sandbox_status()
    assert any("Not available" in line for line in console.lines)
    assert any("Not built" in line for line in console.lines)


def test_sandbox_rebuild_no_docker(monkeypatch):
    monkeypatch.setattr(cli_app, "console", DummyConsole())
    monkeypatch.setattr("tactus.sandbox.is_docker_available", lambda: (False, "missing"))
    import click

    with pytest.raises(click.exceptions.Exit):
        cli_app.sandbox_rebuild()


def test_sandbox_rebuild_missing_dockerfile(monkeypatch, tmp_path):
    monkeypatch.setattr(cli_app, "console", DummyConsole())
    monkeypatch.setattr("tactus.sandbox.is_docker_available", lambda: (True, ""))

    dockerfile = tmp_path / "Dockerfile"
    monkeypatch.setattr(
        "tactus.sandbox.docker_manager.resolve_dockerfile_path",
        lambda path: (dockerfile, "local"),
    )
    monkeypatch.setattr("tactus.sandbox.DockerManager", lambda: FakeManager())

    with pytest.raises(typer.Exit):
        cli_app.sandbox_rebuild()


def test_sandbox_rebuild_up_to_date(monkeypatch, tmp_path):
    console = DummyConsole()
    monkeypatch.setattr(cli_app, "console", console)
    monkeypatch.setattr("tactus.sandbox.is_docker_available", lambda: (True, ""))
    import sys

    monkeypatch.setattr(sys.modules["tactus"], "__version__", "testver", raising=False)

    dockerfile = tmp_path / "Dockerfile"
    dockerfile.write_text("FROM scratch\n")
    monkeypatch.setattr(
        "tactus.sandbox.docker_manager.resolve_dockerfile_path",
        lambda path: (dockerfile, "local"),
    )
    manager = FakeManager(image_exists=True, version="testver")
    monkeypatch.setattr("tactus.sandbox.DockerManager", lambda: manager)

    cli_app.sandbox_rebuild()
    assert manager.build_called is True


def test_sandbox_rebuild_builds(monkeypatch, tmp_path):
    monkeypatch.setattr(cli_app, "console", DummyConsole())
    monkeypatch.setattr("tactus.sandbox.is_docker_available", lambda: (True, ""))

    dockerfile = tmp_path / "Dockerfile"
    dockerfile.write_text("FROM scratch\n")
    monkeypatch.setattr(
        "tactus.sandbox.docker_manager.resolve_dockerfile_path",
        lambda path: (dockerfile, "local"),
    )
    manager = FakeManager(image_exists=False, build_result=(True, "ok"))
    monkeypatch.setattr("tactus.sandbox.DockerManager", lambda: manager)

    cli_app.sandbox_rebuild(verbose=True, force=True)


def test_sandbox_rebuild_pypi_build_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(cli_app, "console", DummyConsole())
    monkeypatch.setattr("tactus.sandbox.is_docker_available", lambda: (True, ""))

    dockerfile = tmp_path / "Dockerfile"
    dockerfile.write_text("FROM scratch\n")
    monkeypatch.setattr(
        "tactus.sandbox.docker_manager.resolve_dockerfile_path",
        lambda path: (dockerfile, "pypi"),
    )
    manager = FakeManager(image_exists=False, build_result=(False, "boom"))
    monkeypatch.setattr("tactus.sandbox.DockerManager", lambda: manager)

    with pytest.raises(typer.Exit):
        cli_app.sandbox_rebuild(verbose=True, force=True)
