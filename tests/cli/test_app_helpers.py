import json
import os
import logging
from pathlib import Path

import pytest
import typer

from tactus.cli import app as cli_app


class DummyConfigManager:
    def __init__(self, tmp_path):
        self._tmp_path = tmp_path
        self.loaded = []

    def _get_system_config_paths(self):
        return [self._tmp_path / "system.yml"]

    def _get_user_config_paths(self):
        return [self._tmp_path / "user.yml"]

    def _load_yaml_file(self, path: Path):
        self.loaded.append(path)
        if path.name == "system.yml":
            return {"api_key": "system"}
        if path.name == "user.yml":
            return {"count": 2}
        if path.name == "config.yml":
            return {
                "features": ["a", "b"],
                "nested": {"region": "us", "enabled": True},
                "mcp_servers": {"skip": True},
            }
        return {}

    def _merge_configs(self, configs):
        merged = {}
        for cfg in configs:
            merged.update(cfg)
        return merged


def test_load_tactus_config_sets_env(monkeypatch, tmp_path):
    (tmp_path / "system.yml").write_text("placeholder")
    (tmp_path / "user.yml").write_text("placeholder")
    project_dir = tmp_path / ".tactus"
    project_dir.mkdir()
    (project_dir / "config.yml").write_text("placeholder")

    dummy_manager = DummyConfigManager(tmp_path)

    monkeypatch.setattr(cli_app, "Path", Path)
    monkeypatch.setattr("tactus.core.config_manager.ConfigManager", lambda: dummy_manager)
    monkeypatch.setenv("COUNT", "existing")

    monkeypatch.chdir(tmp_path)

    merged = cli_app.load_tactus_config()

    assert merged["api_key"] == "system"
    assert merged["count"] == 2
    assert merged["features"] == ["a", "b"]
    assert merged["nested"]["region"] == "us"

    assert os.environ["API_KEY"] == "system"
    assert os.environ["COUNT"] == "existing"
    assert os.environ["FEATURES"] == json.dumps(["a", "b"])
    assert os.environ["NESTED_REGION"] == "us"
    assert os.environ["NESTED_ENABLED"] == "True"


def test_main_callback_version(monkeypatch):
    class DummyCtx:
        invoked_subcommand = None

    monkeypatch.setattr(cli_app.console, "print", lambda *args, **kwargs: None)

    with pytest.raises(typer.Exit):
        cli_app.main_callback(DummyCtx(), version=True)


def test_main_callback_no_subcommand(monkeypatch):
    printed = []

    class DummyCtx:
        invoked_subcommand = None

        def get_help(self):
            return "help"

    monkeypatch.setattr(cli_app.console, "print", lambda msg: printed.append(msg))

    with pytest.raises(typer.Exit):
        cli_app.main_callback(DummyCtx(), version=False)

    assert printed == ["help"]


def test_setup_logging_invalid_log_level():
    with pytest.raises(typer.BadParameter):
        cli_app.setup_logging(log_level="nope")


def test_setup_logging_invalid_log_format():
    with pytest.raises(typer.BadParameter):
        cli_app.setup_logging(log_format="weird")


def test_setup_logging_terminal_handler(monkeypatch):
    captured = {}

    def fake_basic_config(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(logging, "basicConfig", fake_basic_config)

    cli_app.setup_logging(log_format="terminal")

    assert "handlers" in captured
    assert isinstance(captured["handlers"][0], cli_app._TerminalLogHandler)


def test_setup_logging_raw_handler(monkeypatch):
    captured = {}

    def fake_basic_config(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(logging, "basicConfig", fake_basic_config)

    cli_app.setup_logging(log_format="raw")

    assert isinstance(captured["handlers"][0], logging.StreamHandler)


def test_setup_logging_rich_handler(monkeypatch):
    captured = {}

    def fake_basic_config(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(logging, "basicConfig", fake_basic_config)

    cli_app.setup_logging(log_format="rich", verbose=True)

    assert isinstance(captured["handlers"][0], cli_app.RichHandler)


def test_terminal_log_handler_styles(monkeypatch):
    printed = []
    console = cli_app.Console()

    def fake_print(message, style=None, **kwargs):
        printed.append((message, style))

    monkeypatch.setattr(console, "print", fake_print)

    handler = cli_app._TerminalLogHandler(console)

    record = logging.LogRecord("procedure.main", logging.INFO, __file__, 1, "hello", (), None)
    handler.emit(record)

    assert printed
    assert printed[0][0] == "hello"
    assert printed[0][1] == "bold"


def test_terminal_log_handler_warning_and_error(monkeypatch):
    printed = []
    console = cli_app.Console()

    def fake_print(message, style=None, **kwargs):
        printed.append(style)

    monkeypatch.setattr(console, "print", fake_print)

    handler = cli_app._TerminalLogHandler(console)
    warning_record = logging.LogRecord("app", logging.WARNING, __file__, 1, "warn", (), None)
    error_record = logging.LogRecord("app", logging.ERROR, __file__, 1, "err", (), None)

    handler.emit(warning_record)
    handler.emit(error_record)

    assert "yellow" in printed
    assert "bold red" in printed


def test_terminal_log_handler_handle_error(monkeypatch):
    console = cli_app.Console()
    handler = cli_app._TerminalLogHandler(console)
    seen = {"error": False}

    def fail_print(*_args, **_kwargs):
        raise RuntimeError("boom")

    def handle_error(_record):
        seen["error"] = True

    monkeypatch.setattr(console, "print", fail_print)
    monkeypatch.setattr(handler, "handleError", handle_error)

    record = logging.LogRecord("app", logging.INFO, __file__, 1, "msg", (), None)
    handler.emit(record)

    assert seen["error"] is True
