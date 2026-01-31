import io

import pytest
import typer

from tactus.cli import app as cli_app


class DummyValidationResult:
    def __init__(self, valid=True, warnings=None, errors=None, registry=None):
        self.valid = valid
        self.warnings = warnings or []
        self.errors = errors or []
        self.registry = registry


class DummyWarning:
    def __init__(self, message):
        self.message = message


class DummyError:
    def __init__(self, message):
        self.message = message


class DummyAgent:
    def __init__(self, provider, model, system_prompt, tools=None):
        self.provider = provider
        self.model = model
        self.system_prompt = system_prompt
        self.tools = tools or []


class DummyRegistry:
    def __init__(self):
        self.description = "demo"
        self.agents = {
            "alpha": DummyAgent("openai", "gpt-4o", "hello", tools=["done"]),
            "beta": DummyAgent("bedrock", {"name": "sonnet"}, "prompt" * 40),
            "gamma": DummyAgent("openai", 123, ""),
            "delta": DummyAgent("openai", None, "hi"),
        }
        self.output_schema = {
            "out1": {"type": "string", "required": True},
            "out2": None,
            "out3": "string",
        }
        self.input_schema = {
            "param1": {"type": "string", "required": True, "default": "x"},
            "param2": None,
            "param3": 123,
        }
        self.specifications = ["scenario a"]


class DummyValidator:
    def __init__(self, result):
        self._result = result

    def validate(self, _source, _mode):
        return self._result

    def validate_file(self, _path):
        return self._result


def test_validate_missing_file(tmp_path):
    missing = tmp_path / "missing.tac"
    with pytest.raises(typer.Exit):
        cli_app.validate(missing, verbose=False, quick=False)


def test_validate_lua_valid(monkeypatch, tmp_path):
    workflow = tmp_path / "workflow.tac"
    workflow.write_text("print('hi')")

    result = DummyValidationResult(
        valid=True,
        warnings=[DummyWarning("be careful")],
        registry=DummyRegistry(),
    )
    monkeypatch.setattr(cli_app, "TactusValidator", lambda: DummyValidator(result))
    monkeypatch.setattr(cli_app.console, "print", lambda *_args, **_kwargs: None)

    cli_app.validate(workflow, verbose=False, quick=False)


def test_validate_lua_invalid(monkeypatch, tmp_path):
    workflow = tmp_path / "workflow.tac"
    workflow.write_text("print('hi')")

    result = DummyValidationResult(
        valid=False,
        errors=[DummyError("bad")],
    )
    monkeypatch.setattr(cli_app, "TactusValidator", lambda: DummyValidator(result))
    monkeypatch.setattr(cli_app.console, "print", lambda *_args, **_kwargs: None)

    with pytest.raises(typer.Exit):
        cli_app.validate(workflow, verbose=False, quick=True)


def test_validate_yaml_success(monkeypatch, tmp_path):
    workflow = tmp_path / "workflow.yaml"
    workflow.write_text("name: demo")

    monkeypatch.setattr(
        "tactus.core.yaml_parser.ProcedureYAMLParser.parse",
        lambda _source: {"name": "demo", "agents": {"a": {"system_prompt": "hi"}}},
    )
    monkeypatch.setattr(cli_app.console, "print", lambda *_args, **_kwargs: None)

    cli_app.validate(workflow, verbose=False, quick=False)


def test_validate_yaml_parse_error(monkeypatch, tmp_path):
    workflow = tmp_path / "workflow.yaml"
    workflow.write_text("name: demo")

    monkeypatch.setattr(
        "tactus.core.yaml_parser.ProcedureYAMLParser.parse",
        lambda _source: (_ for _ in ()).throw(cli_app.ProcedureConfigError("bad")),
    )
    monkeypatch.setattr(cli_app.console, "print", lambda *_args, **_kwargs: None)

    with pytest.raises(typer.Exit):
        cli_app.validate(workflow, verbose=False, quick=False)


def test_format_stdout(monkeypatch, tmp_path):
    workflow = tmp_path / "workflow.tac"
    workflow.write_text("print('hi')")

    class DummyResult:
        changed = True
        formatted = "formatted"

    monkeypatch.setattr(
        "tactus.formatting.TactusFormatter.format_source", lambda _self, _src: DummyResult()
    )

    buffer = io.StringIO()
    monkeypatch.setattr(cli_app.sys, "stdout", buffer)

    cli_app.format_(workflow, check=False, stdout=True)
    assert buffer.getvalue() == "formatted"


def test_format_missing_file(tmp_path):
    missing = tmp_path / "missing.tac"
    with pytest.raises(typer.Exit):
        cli_app.format_(missing, check=False, stdout=False)


def test_format_check_mode_changed(monkeypatch, tmp_path):
    workflow = tmp_path / "workflow.tac"
    workflow.write_text("print('hi')")

    class DummyResult:
        changed = True
        formatted = "formatted"

    monkeypatch.setattr(
        "tactus.formatting.TactusFormatter.format_source", lambda _self, _src: DummyResult()
    )
    monkeypatch.setattr(cli_app.console, "print", lambda *_args, **_kwargs: None)

    with pytest.raises(typer.Exit):
        cli_app.format_(workflow, check=True, stdout=False)


def test_format_check_mode_no_changes(monkeypatch, tmp_path):
    workflow = tmp_path / "workflow.tac"
    workflow.write_text("print('hi')")

    class DummyResult:
        changed = False
        formatted = "same"

    monkeypatch.setattr(
        "tactus.formatting.TactusFormatter.format_source", lambda _self, _src: DummyResult()
    )
    monkeypatch.setattr(cli_app.console, "print", lambda *_args, **_kwargs: None)

    cli_app.format_(workflow, check=True, stdout=False)


def test_format_write_and_no_changes(monkeypatch, tmp_path):
    workflow = tmp_path / "workflow.tac"
    workflow.write_text("print('hi')")

    class ChangedResult:
        changed = True
        formatted = "formatted"

    class UnchangedResult:
        changed = False
        formatted = "same"

    monkeypatch.setattr(
        "tactus.formatting.TactusFormatter.format_source", lambda _self, _src: ChangedResult()
    )
    monkeypatch.setattr(cli_app.console, "print", lambda *_args, **_kwargs: None)
    cli_app.format_(workflow, check=False, stdout=False)
    assert workflow.read_text() == "formatted"

    monkeypatch.setattr(
        "tactus.formatting.TactusFormatter.format_source", lambda _self, _src: UnchangedResult()
    )
    cli_app.format_(workflow, check=False, stdout=False)


def test_format_invalid_extension(tmp_path):
    workflow = tmp_path / "workflow.yaml"
    workflow.write_text("name: demo")
    with pytest.raises(typer.Exit):
        cli_app.format_(workflow, check=False, stdout=False)


def test_format_raises_formatting_error(monkeypatch, tmp_path):
    workflow = tmp_path / "workflow.tac"
    workflow.write_text("print('hi')")

    monkeypatch.setattr(
        "tactus.formatting.TactusFormatter.format_source",
        lambda _self, _src: (_ for _ in ()).throw(cli_app.FormattingError("boom")),
    )
    monkeypatch.setattr(cli_app.console, "print", lambda *_args, **_kwargs: None)

    with pytest.raises(typer.Exit):
        cli_app.format_(workflow, check=False, stdout=False)


def test_info_invalid_file(tmp_path):
    missing = tmp_path / "missing.tac"
    with pytest.raises(typer.Exit):
        cli_app.info(missing)


def test_info_non_lua(monkeypatch, tmp_path):
    workflow = tmp_path / "workflow.yaml"
    workflow.write_text("name: demo")
    monkeypatch.setattr(cli_app.console, "print", lambda *_args, **_kwargs: None)
    with pytest.raises(typer.Exit):
        cli_app.info(workflow)


def test_info_invalid_registry(monkeypatch, tmp_path):
    workflow = tmp_path / "workflow.tac"
    workflow.write_text("print('hi')")

    result = DummyValidationResult(valid=False, errors=[DummyError("bad")])
    monkeypatch.setattr(cli_app, "TactusValidator", lambda: DummyValidator(result))
    monkeypatch.setattr(cli_app.console, "print", lambda *_args, **_kwargs: None)

    with pytest.raises(typer.Exit):
        cli_app.info(workflow)


def test_info_valid(monkeypatch, tmp_path):
    workflow = tmp_path / "workflow.tac"
    workflow.write_text("print('hi')")

    result = DummyValidationResult(valid=True, registry=DummyRegistry())
    monkeypatch.setattr(cli_app, "TactusValidator", lambda: DummyValidator(result))
    monkeypatch.setattr(cli_app.console, "print", lambda *_args, **_kwargs: None)

    cli_app.info(workflow)


def test_info_valid_without_optional_sections(monkeypatch, tmp_path):
    workflow = tmp_path / "workflow.tac"
    workflow.write_text("print('hi')")

    registry = DummyRegistry()
    registry.description = ""
    registry.agents = {}
    registry.input_schema = {}
    registry.output_schema = {}
    registry.specifications = []

    result = DummyValidationResult(valid=True, registry=registry)
    monkeypatch.setattr(cli_app, "TactusValidator", lambda: DummyValidator(result))
    monkeypatch.setattr(cli_app.console, "print", lambda *_args, **_kwargs: None)

    cli_app.info(workflow)
