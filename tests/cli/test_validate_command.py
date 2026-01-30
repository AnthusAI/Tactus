import pytest

from tactus.cli import app as cli_app


class DummyConsole:
    def __init__(self):
        self.lines = []

    def print(self, *args, **kwargs):
        self.lines.append(" ".join(str(a) for a in args))

    def print_exception(self):
        self.lines.append("exception")


class FakeResult:
    def __init__(self, valid=True, warnings=None, errors=None, registry=None):
        self.valid = valid
        self.warnings = warnings or []
        self.errors = errors or []
        self.registry = registry


class FakeValidator:
    def __init__(self, result):
        self._result = result

    def validate(self, content, mode=None):
        return self._result


def test_validate_command_success(monkeypatch, tmp_path):
    console = DummyConsole()
    monkeypatch.setattr(cli_app, "console", console)
    monkeypatch.setattr(cli_app, "setup_logging", lambda verbose: None)
    monkeypatch.setattr(cli_app, "TactusValidator", lambda: FakeValidator(FakeResult()))

    path = tmp_path / "sample.tac"
    path.write_text("content")
    cli_app.validate(path)
    assert any("Validating" in line for line in console.lines)


def test_validate_command_failure(monkeypatch, tmp_path):
    import click

    console = DummyConsole()
    monkeypatch.setattr(cli_app, "console", console)
    monkeypatch.setattr(cli_app, "setup_logging", lambda verbose: None)
    monkeypatch.setattr(
        cli_app,
        "TactusValidator",
        lambda: FakeValidator(
            FakeResult(
                valid=False, errors=[type("Err", (), {"message": "bad", "location": None})()]
            )
        ),
    )

    path = tmp_path / "sample.tac"
    path.write_text("content")
    with pytest.raises(click.exceptions.Exit):
        cli_app.validate(path)
