import io

from rich.console import Console

from tactus.cli import app as cli_app


def test_parse_value_variants():
    assert cli_app._parse_value("true", "boolean") is True
    assert cli_app._parse_value("0", "boolean") is False
    assert cli_app._parse_value("3", "number") == 3
    assert cli_app._parse_value("3.5", "number") == 3.5
    assert cli_app._parse_value("nope", "number") == 0
    assert cli_app._parse_value("[1, 2]", "array") == [1, 2]
    assert cli_app._parse_value("a,b", "array") == ["a", "b"]
    assert cli_app._parse_value("", "array") == []
    assert cli_app._parse_value('{"a": 1}', "object") == {"a": 1}
    assert cli_app._parse_value("nope", "object") == {}
    assert cli_app._parse_value("hi", "string") == "hi"


def test_prompt_for_inputs_handles_all_types(monkeypatch):
    console = Console(file=io.StringIO(), force_terminal=False)

    answers = iter(
        [
            "nope",
            "2",
            "a,b",
            "[]",
            "{bad json",
            "7.5",
            "hello",
        ]
    )

    monkeypatch.setattr(cli_app.Confirm, "ask", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(cli_app.Prompt, "ask", lambda *_args, **_kwargs: next(answers))

    input_schema = {
        "flag": {"type": "boolean", "required": True},
        "mode": {"enum": ["one", "two"], "default": "one"},
        "items": {"type": "array", "default": [1]},
        "empty_items": {"type": "array"},
        "meta": {"type": "object", "default": {"a": 1}},
        "count": {"type": "number", "default": 3},
        "note": {"type": "string", "description": "msg"},
    }

    resolved = cli_app._prompt_for_inputs(console, input_schema, {})

    assert resolved["flag"] is True
    assert resolved["mode"] == "two"
    assert resolved["items"] == ["a", "b"]
    assert resolved["empty_items"] == []
    assert resolved["meta"] == {}
    assert resolved["count"] == 7.5
    assert resolved["note"] == "hello"


def test_prompt_for_inputs_handles_provided_and_defaults(monkeypatch):
    console = Console(file=io.StringIO(), force_terminal=False)

    monkeypatch.setattr(cli_app.Confirm, "ask", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(cli_app.Prompt, "ask", lambda *_args, **_kwargs: "value")

    input_schema = {"flag": {"type": "boolean"}, "text": {"type": "string"}}
    provided = {"text": "preset"}

    resolved = cli_app._prompt_for_inputs(console, input_schema, provided)

    assert resolved["flag"] is False
    assert resolved["text"] == "value"


def test_prompt_for_inputs_empty_schema():
    console = Console(file=io.StringIO(), force_terminal=False)
    assert cli_app._prompt_for_inputs(console, {}, {"a": 1}) == {"a": 1}


def test_check_missing_required_inputs():
    schema = {
        "a": {"required": True},
        "b": {"required": True, "default": 1},
        "c": {"required": False},
    }
    assert cli_app._check_missing_required_inputs(schema, {"a": 1}) == []
    assert cli_app._check_missing_required_inputs(schema, {}) == ["a"]
