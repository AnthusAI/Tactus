from tactus.validation.validator import TactusValidator, ValidationMode


def test_validate_quick_mode_skips_registry():
    source = """
    name = "Demo"
    """

    result = TactusValidator().validate(source, mode=ValidationMode.QUICK)

    assert result.valid is True
    assert result.registry is None


def test_validate_file_missing():
    result = TactusValidator().validate_file("missing.tac", mode=ValidationMode.FULL)

    assert result.valid is False
    assert any("File not found" in err.message for err in result.errors)


def test_validate_file_reads(tmp_path):
    path = tmp_path / "simple.tac"
    path.write_text("name = 'Demo'", encoding="utf-8")

    result = TactusValidator().validate_file(str(path), mode=ValidationMode.QUICK)

    assert result.valid is True
