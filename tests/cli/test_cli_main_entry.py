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


def test_main_does_not_insert_before_train_subcommand(monkeypatch):
    called = {"app": False}

    def fake_app():
        called["app"] = True

    monkeypatch.setattr(cli_app, "load_tactus_config", lambda: None)
    monkeypatch.setattr(cli_app, "app", fake_app)
    monkeypatch.setattr(sys, "argv", ["tactus", "train", "config.tac"])

    cli_app.main()

    assert called["app"] is True
    assert sys.argv[1] == "train"
    assert sys.argv[2] == "config.tac"


def test_main_inserts_run_for_tac_without_requiring_file_exists(monkeypatch, tmp_path):
    """Regression: must work when cwd does not resolve the path before run()."""
    called = {"app": False}

    def fake_app():
        called["app"] = True

    monkeypatch.setattr(cli_app, "load_tactus_config", lambda: None)
    monkeypatch.setattr(cli_app, "app", fake_app)
    monkeypatch.setattr(sys, "argv", ["tactus", "nested/procedure.tac"])

    cli_app.main()

    assert sys.argv[:3] == ["tactus", "run", "nested/procedure.tac"]
    assert called["app"] is True
