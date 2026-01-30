import threading
import time
import types
import webbrowser

import pytest
import typer

from tactus.cli import app as cli_app


class DummyThread:
    def __init__(self, target, daemon=True):
        self.target = target
        self.daemon = daemon

    def start(self):
        self.target()


class DummyApp:
    def run(self, *args, **kwargs):
        return None


def _setup_ide_paths(monkeypatch, tmp_path, *, dist_exists=True, frontend_exists=True):
    fake_file = tmp_path / "tactus" / "cli" / "app.py"
    fake_file.parent.mkdir(parents=True, exist_ok=True)
    fake_file.write_text("placeholder")
    monkeypatch.setattr(cli_app, "__file__", str(fake_file))

    frontend_dir = tmp_path / "tactus-ide" / "frontend"
    dist_dir = frontend_dir / "dist"
    if frontend_exists:
        frontend_dir.mkdir(parents=True, exist_ok=True)
    if dist_exists:
        dist_dir.mkdir(parents=True, exist_ok=True)

    return frontend_dir, dist_dir


def test_ide_starts_with_existing_dist(monkeypatch, tmp_path):
    _setup_ide_paths(monkeypatch, tmp_path, dist_exists=True, frontend_exists=True)

    sleep_calls = {"count": 0}

    def fake_sleep(_seconds):
        sleep_calls["count"] += 1
        if sleep_calls["count"] >= 2:
            raise KeyboardInterrupt()

    monkeypatch.setattr(cli_app, "setup_logging", lambda verbose: None)
    monkeypatch.setattr(threading, "Thread", DummyThread)
    monkeypatch.setattr(time, "sleep", fake_sleep)
    monkeypatch.setattr(webbrowser, "open", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("tactus.ide.create_app", lambda **_kwargs: DummyApp())
    monkeypatch.setattr(cli_app.console, "print", lambda *_args, **_kwargs: None)

    cli_app.ide(port=0, no_browser=True, verbose=False)


def test_ide_build_fails_when_frontend_missing(monkeypatch, tmp_path):
    _setup_ide_paths(monkeypatch, tmp_path, dist_exists=False, frontend_exists=False)

    monkeypatch.setattr(cli_app, "setup_logging", lambda verbose: None)
    monkeypatch.setattr(cli_app.console, "print", lambda *_args, **_kwargs: None)

    with pytest.raises(typer.Exit):
        cli_app.ide(port=0, no_browser=True, verbose=False)


def test_ide_build_error_from_npm(monkeypatch, tmp_path):
    _setup_ide_paths(monkeypatch, tmp_path, dist_exists=False, frontend_exists=True)

    class FakeResult:
        returncode = 1
        stderr = "build error"

    import subprocess as subprocess_module

    monkeypatch.setattr(cli_app, "setup_logging", lambda verbose: None)
    monkeypatch.setattr(subprocess_module, "run", lambda *args, **kwargs: FakeResult())
    monkeypatch.setattr(threading, "Thread", DummyThread)
    monkeypatch.setattr(time, "sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(webbrowser, "open", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("tactus.ide.create_app", lambda **_kwargs: DummyApp())
    monkeypatch.setattr(cli_app.console, "print", lambda *_args, **_kwargs: None)

    with pytest.raises(typer.Exit):
        cli_app.ide(port=0, no_browser=True, verbose=False)


def test_ide_build_missing_npm(monkeypatch, tmp_path):
    _setup_ide_paths(monkeypatch, tmp_path, dist_exists=False, frontend_exists=True)

    def raise_missing(*_args, **_kwargs):
        raise FileNotFoundError("npm")

    import subprocess as subprocess_module

    monkeypatch.setattr(cli_app, "setup_logging", lambda verbose: None)
    monkeypatch.setattr(subprocess_module, "run", raise_missing)
    monkeypatch.setattr(threading, "Thread", DummyThread)
    monkeypatch.setattr(time, "sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(webbrowser, "open", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("tactus.ide.create_app", lambda **_kwargs: DummyApp())
    monkeypatch.setattr(cli_app.console, "print", lambda *_args, **_kwargs: None)

    with pytest.raises(typer.Exit):
        cli_app.ide(port=0, no_browser=True, verbose=False)
