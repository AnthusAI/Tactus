import asyncio
import sys

from typer.testing import CliRunner

from tactus.cli import app as cli_app


def test_main_inserts_run_for_file_argument(monkeypatch, tmp_path):
    workflow = tmp_path / "flow.tac"
    workflow.write_text("content")

    called = {}

    def fake_app():
        called["ran"] = True

    monkeypatch.setattr(cli_app, "load_tactus_config", lambda: None)
    monkeypatch.setattr(cli_app, "app", fake_app)
    monkeypatch.setattr(sys, "argv", ["tactus", str(workflow)])

    cli_app.main()

    assert sys.argv[1] == "run"
    assert called["ran"] is True


def test_control_command_multiple_sockets(monkeypatch):
    sockets = ["/tmp/t1.sock", "/tmp/t2.sock"]
    monkeypatch.setattr("glob.glob", lambda pattern: sockets)
    monkeypatch.setattr(cli_app.Prompt, "ask", lambda *args, **kwargs: "2")

    called = {}

    async def fake_control_main(socket_path, auto_respond):
        called["socket"] = socket_path
        called["respond"] = auto_respond

    monkeypatch.setattr("tactus.cli.control.main", fake_control_main)

    def fake_asyncio_run(coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    monkeypatch.setattr(asyncio, "run", fake_asyncio_run)

    runner = CliRunner()
    result = runner.invoke(cli_app.app, ["control"])

    assert result.exit_code == 0
    assert called["socket"] == "/tmp/t2.sock"


def test_control_command_single_socket(monkeypatch):
    sockets = ["/tmp/only.sock"]
    monkeypatch.setattr("glob.glob", lambda pattern: sockets)

    called = {}

    async def fake_control_main(socket_path, auto_respond):
        called["socket"] = socket_path

    monkeypatch.setattr("tactus.cli.control.main", fake_control_main)

    def fake_asyncio_run(coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    monkeypatch.setattr(asyncio, "run", fake_asyncio_run)

    runner = CliRunner()
    result = runner.invoke(cli_app.app, ["control"])

    assert result.exit_code == 0
    assert called["socket"] == "/tmp/only.sock"


def test_control_command_no_sockets(monkeypatch):
    monkeypatch.setattr("glob.glob", lambda pattern: [])
    runner = CliRunner()
    result = runner.invoke(cli_app.app, ["control"])
    assert result.exit_code == 1


def test_control_command_with_socket_path(monkeypatch):
    called = {}

    async def fake_control_main(socket_path, auto_respond):
        called["socket"] = socket_path
        called["respond"] = auto_respond

    monkeypatch.setattr("tactus.cli.control.main", fake_control_main)

    def fake_asyncio_run(coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    monkeypatch.setattr(asyncio, "run", fake_asyncio_run)

    runner = CliRunner()
    result = runner.invoke(cli_app.app, ["control", "--socket", "/tmp/explicit.sock"])

    assert result.exit_code == 0
    assert called["socket"] == "/tmp/explicit.sock"


def test_main_does_not_insert_for_subcommand(monkeypatch):
    called = {}

    def fake_app():
        called["ran"] = True

    monkeypatch.setattr(cli_app, "load_tactus_config", lambda: None)
    monkeypatch.setattr(cli_app, "app", fake_app)
    monkeypatch.setattr(sys, "argv", ["tactus", "run", "file.tac"])

    cli_app.main()

    assert sys.argv[1] == "run"
    assert called["ran"] is True


def test_main_does_not_insert_for_missing_file(monkeypatch, tmp_path):
    called = {}

    def fake_app():
        called["ran"] = True

    missing = tmp_path / "missing.tac"

    monkeypatch.setattr(cli_app, "load_tactus_config", lambda: None)
    monkeypatch.setattr(cli_app, "app", fake_app)
    monkeypatch.setattr(sys, "argv", ["tactus", str(missing)])

    cli_app.main()

    assert sys.argv[1] == str(missing)
    assert called["ran"] is True


def test_main_does_not_insert_for_option(monkeypatch):
    called = {}

    def fake_app():
        called["ran"] = True

    monkeypatch.setattr(cli_app, "load_tactus_config", lambda: None)
    monkeypatch.setattr(cli_app, "app", fake_app)
    monkeypatch.setattr(sys, "argv", ["tactus", "--help"])

    cli_app.main()

    assert sys.argv[1] == "--help"
    assert called["ran"] is True


def test_main_handles_no_args(monkeypatch):
    called = {}

    def fake_app():
        called["ran"] = True

    monkeypatch.setattr(cli_app, "load_tactus_config", lambda: None)
    monkeypatch.setattr(cli_app, "app", fake_app)
    monkeypatch.setattr(sys, "argv", ["tactus"])

    cli_app.main()

    assert sys.argv == ["tactus"]
    assert called["ran"] is True
