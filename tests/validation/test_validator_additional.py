import builtins

from tactus.validation.validator import TactusValidator, ValidationMode


def test_validate_file_missing_returns_error(tmp_path):
    validator = TactusValidator()
    result = validator.validate_file(str(tmp_path / "missing.tac"), ValidationMode.FULL)

    assert result.valid is False
    assert "File not found" in result.errors[0].message


def test_validate_file_read_error(monkeypatch, tmp_path):
    validator = TactusValidator()

    def fake_open(*_args, **_kwargs):
        raise OSError("boom")

    monkeypatch.setattr(builtins, "open", fake_open)

    result = validator.validate_file(str(tmp_path / "file.tac"), ValidationMode.FULL)

    assert result.valid is False
    assert "Error reading file" in result.errors[0].message


def test_validate_handles_unexpected_exception(monkeypatch):
    validator = TactusValidator()

    class BrokenLexer:
        def __init__(self, *_args, **_kwargs):
            raise RuntimeError("lexer failed")

    monkeypatch.setattr("tactus.validation.validator.LuaLexer", BrokenLexer)

    result = validator.validate('Agent "a" {}', ValidationMode.FULL)

    assert result.valid is False
    assert "Validation error" in result.errors[0].message
