import sys

from tactus.cli import app as cli_app


def test_main_inserts_run_for_direct_file(monkeypatch, tmp_path):
    workflow = tmp_path / "workflow.tac"
    workflow.write_text("content")

    called = {"app": False}

    def fake_app():
        called["app"] = True

    monkeypatch.setattr(cli_app, "load_tactus_config", lambda: None)
    monkeypatch.setattr(cli_app, "app", fake_app)
    monkeypatch.setattr(sys, "argv", ["tactus", str(workflow)])

    cli_app.main()

    assert called["app"] is True
    assert sys.argv[1] == "run"
    assert sys.argv[2] == str(workflow)


def test_main_does_not_insert_for_subcommand(monkeypatch):
    called = {"app": False}

    def fake_app():
        called["app"] = True

    monkeypatch.setattr(cli_app, "load_tactus_config", lambda: None)
    monkeypatch.setattr(cli_app, "app", fake_app)
    monkeypatch.setattr(sys, "argv", ["tactus", "run", "file.tac"])

    cli_app.main()

    assert called["app"] is True
    assert sys.argv[1] == "run"
