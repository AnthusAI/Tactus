import sys

from tactus.cli import app as cli_app


class DummyConsole:
    def __init__(self):
        self.lines = []

    def print(self, *args, **kwargs):
        self.lines.append(" ".join(str(a) for a in args))


def test_version_command(monkeypatch):
    console = DummyConsole()
    monkeypatch.setattr(cli_app, "console", console)
    monkeypatch.setattr(sys.modules["tactus"], "__version__", "1.2.3", raising=False)
    cli_app.version()
    assert "1.2.3" in console.lines[0]
