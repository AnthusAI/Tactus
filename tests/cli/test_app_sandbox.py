import pytest
import typer

from tactus.cli import app as cli_app


class DummyDockerManager:
    def __init__(self, image_exists=True, version="dev", build_success=True):
        self._image_exists = image_exists
        self._version = version
        self._build_success = build_success
        self.full_image_name = "tactus-sandbox:local"

    def image_exists(self):
        return self._image_exists

    def get_image_version(self):
        return self._version

    def build_image(self, **_kwargs):
        return self._build_success, "error"


def test_sandbox_status_available(monkeypatch):
    monkeypatch.setattr("tactus.sandbox.is_docker_available", lambda: (True, ""))
    monkeypatch.setattr("tactus.sandbox.DockerManager", lambda: DummyDockerManager())
    monkeypatch.setattr(cli_app.console, "print", lambda *_args, **_kwargs: None)

    cli_app.sandbox_status()


def test_sandbox_status_unavailable(monkeypatch):
    monkeypatch.setattr("tactus.sandbox.is_docker_available", lambda: (False, "nope"))
    monkeypatch.setattr("tactus.sandbox.DockerManager", lambda: DummyDockerManager())
    monkeypatch.setattr(cli_app.console, "print", lambda *_args, **_kwargs: None)

    cli_app.sandbox_status()


def test_sandbox_rebuild_no_docker(monkeypatch):
    monkeypatch.setattr("tactus.sandbox.is_docker_available", lambda: (False, "nope"))
    monkeypatch.setattr(cli_app.console, "print", lambda *_args, **_kwargs: None)

    with pytest.raises(typer.Exit):
        cli_app.sandbox_rebuild(verbose=False, force=False)


def test_sandbox_rebuild_up_to_date(monkeypatch, tmp_path):
    dummy_manager = DummyDockerManager(image_exists=True, version="1.0.0")
    dummy_file = tmp_path / "Dockerfile"
    dummy_file.write_text("FROM scratch")

    monkeypatch.setattr("tactus.sandbox.is_docker_available", lambda: (True, ""))
    monkeypatch.setattr("tactus.sandbox.DockerManager", lambda: dummy_manager)
    monkeypatch.setattr(
        "tactus.sandbox.docker_manager.resolve_dockerfile_path",
        lambda _path: (dummy_file, "dev"),
    )
    monkeypatch.setattr(cli_app.console, "print", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("tactus.__version__", "1.0.0")
    monkeypatch.setattr("tactus.__file__", str(tmp_path / "__init__.py"))

    cli_app.sandbox_rebuild(verbose=False, force=False)


def test_sandbox_rebuild_missing_dockerfile(monkeypatch, tmp_path):
    dummy_file = tmp_path / "Dockerfile"

    monkeypatch.setattr("tactus.sandbox.is_docker_available", lambda: (True, ""))
    monkeypatch.setattr("tactus.sandbox.DockerManager", lambda: DummyDockerManager())
    monkeypatch.setattr(
        "tactus.sandbox.docker_manager.resolve_dockerfile_path",
        lambda _path: (dummy_file, "dev"),
    )
    monkeypatch.setattr(cli_app.console, "print", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("tactus.__file__", str(tmp_path / "__init__.py"))

    with pytest.raises(typer.Exit):
        cli_app.sandbox_rebuild(verbose=False, force=False)


def test_sandbox_rebuild_success(monkeypatch, tmp_path):
    dummy_file = tmp_path / "Dockerfile"
    dummy_file.write_text("FROM scratch")

    dummy_manager = DummyDockerManager(image_exists=False, build_success=True)

    monkeypatch.setattr("tactus.sandbox.is_docker_available", lambda: (True, ""))
    monkeypatch.setattr("tactus.sandbox.DockerManager", lambda: dummy_manager)
    monkeypatch.setattr(
        "tactus.sandbox.docker_manager.resolve_dockerfile_path",
        lambda _path: (dummy_file, "pypi"),
    )
    monkeypatch.setattr(cli_app.console, "print", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("tactus.__version__", "2.0.0")
    monkeypatch.setattr("tactus.__file__", str(tmp_path / "__init__.py"))

    cli_app.sandbox_rebuild(verbose=True, force=True)


def test_sandbox_rebuild_version_mismatch(monkeypatch, tmp_path):
    dummy_file = tmp_path / "Dockerfile"
    dummy_file.write_text("FROM scratch")

    dummy_manager = DummyDockerManager(image_exists=True, version="1.0.0", build_success=True)

    monkeypatch.setattr("tactus.sandbox.is_docker_available", lambda: (True, ""))
    monkeypatch.setattr("tactus.sandbox.DockerManager", lambda: dummy_manager)
    monkeypatch.setattr(
        "tactus.sandbox.docker_manager.resolve_dockerfile_path",
        lambda _path: (dummy_file, "dev"),
    )
    monkeypatch.setattr(cli_app.console, "print", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("tactus.__version__", "2.0.0")
    monkeypatch.setattr("tactus.__file__", str(tmp_path / "__init__.py"))

    cli_app.sandbox_rebuild(verbose=False, force=False)


def test_sandbox_rebuild_failure(monkeypatch, tmp_path):
    dummy_file = tmp_path / "Dockerfile"
    dummy_file.write_text("FROM scratch")

    dummy_manager = DummyDockerManager(image_exists=False, build_success=False)

    monkeypatch.setattr("tactus.sandbox.is_docker_available", lambda: (True, ""))
    monkeypatch.setattr("tactus.sandbox.DockerManager", lambda: dummy_manager)
    monkeypatch.setattr(
        "tactus.sandbox.docker_manager.resolve_dockerfile_path",
        lambda _path: (dummy_file, "dev"),
    )
    monkeypatch.setattr(cli_app.console, "print", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("tactus.__file__", str(tmp_path / "__init__.py"))

    with pytest.raises(typer.Exit):
        cli_app.sandbox_rebuild(verbose=False, force=True)
