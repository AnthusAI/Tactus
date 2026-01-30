import logging

import pytest
import typer

from tactus.cli import app as cli_app


class DummyConsole:
    def __init__(self):
        self.calls = []

    def print(self, message, style=None, markup=None, highlight=None):
        self.calls.append(
            {
                "message": message,
                "style": style,
                "markup": markup,
                "highlight": highlight,
            }
        )


def _make_record(name: str, level: int, message: str) -> logging.LogRecord:
    return logging.LogRecord(
        name=name,
        level=level,
        pathname=__file__,
        lineno=1,
        msg=message,
        args=(),
        exc_info=None,
    )


def test_terminal_log_handler_styles():
    console = DummyConsole()
    handler = cli_app._TerminalLogHandler(console)

    handler.emit(_make_record("procedure.test", logging.INFO, "proc"))
    handler.emit(_make_record("test", logging.ERROR, "err"))
    handler.emit(_make_record("test", logging.WARNING, "warn"))
    handler.emit(_make_record("test", logging.DEBUG, "debug"))
    handler.emit(_make_record("test", logging.INFO, "info"))

    styles = [call["style"] for call in console.calls]
    assert styles == ["bold", "bold red", "yellow", "dim", ""]


def test_setup_logging_invalid_level():
    with pytest.raises(typer.BadParameter):
        cli_app.setup_logging(log_level="nope")


def test_setup_logging_invalid_format():
    with pytest.raises(typer.BadParameter):
        cli_app.setup_logging(log_format="nope")


def test_setup_logging_raw_and_terminal():
    cli_app.setup_logging(log_format="raw")
    cli_app.setup_logging(log_format="terminal")
