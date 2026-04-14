import os

from tactus.cli import dotenv_loader


def test_load_dotenv_in_directory_reads_env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text('DOTENV_TEST_FROM_FILE="hello"\n')
    dotenv_loader.load_dotenv_in_directory(tmp_path)
    assert os.environ["DOTENV_TEST_FROM_FILE"] == "hello"


def test_load_dotenv_does_not_override_existing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("DOTENV_TEST_OVERRIDE=from_file\n")
    monkeypatch.setenv("DOTENV_TEST_OVERRIDE", "from_shell")
    dotenv_loader.load_dotenv_in_directory(tmp_path)
    assert os.environ["DOTENV_TEST_OVERRIDE"] == "from_shell"


def test_load_dotenv_next_to_procedure_uses_parent_dir(tmp_path, monkeypatch):
    sub = tmp_path / "proj"
    sub.mkdir()
    tac = sub / "p.tac"
    tac.write_text("-- empty")
    (sub / ".env").write_text("DOTENV_TEST_PROC=1\n")
    monkeypatch.chdir(tmp_path)
    dotenv_loader.load_dotenv_next_to_procedure(tac)
    assert os.environ["DOTENV_TEST_PROC"] == "1"
