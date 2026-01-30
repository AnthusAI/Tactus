from tactus.cli import app as cli_app


def test_parse_value_variants():
    assert cli_app._parse_value("yes", "boolean") is True
    assert cli_app._parse_value("no", "boolean") is False
    assert cli_app._parse_value("3", "number") == 3
    assert cli_app._parse_value("3.5", "number") == 3.5
    assert cli_app._parse_value("bad", "number") == 0
    assert cli_app._parse_value("[1,2]", "array") == [1, 2]
    assert cli_app._parse_value("a,b", "array") == ["a", "b"]
    assert cli_app._parse_value("", "array") == []
    assert cli_app._parse_value('{"x":1}', "object") == {"x": 1}
    assert cli_app._parse_value("bad", "object") == {}
    assert cli_app._parse_value("text", "string") == "text"


def test_check_missing_required_inputs():
    schema = {
        "name": {"type": "string", "required": True},
        "age": {"type": "number", "required": True, "default": 0},
    }
    missing = cli_app._check_missing_required_inputs(schema, provided_params={})

    assert missing == ["name"]


def test_prompt_for_inputs(monkeypatch):
    responses = [
        "3",  # invalid enum choice
        "2",  # valid enum choice
        "1,2,3",  # array
        '{"x": 1}',  # object
        "5",  # number
        "Bob",  # string
    ]

    def fake_prompt(*_args, **_kwargs):
        return responses.pop(0)

    monkeypatch.setattr(cli_app.Prompt, "ask", fake_prompt)
    monkeypatch.setattr(cli_app.Confirm, "ask", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(cli_app.console, "print", lambda *_args, **_kwargs: None)

    input_schema = {
        "flag": {"type": "boolean", "required": True, "default": True},
        "choice": {"enum": ["a", "b"], "default": "b"},
        "items": {"type": "array", "default": [1]},
        "config": {"type": "object"},
        "count": {"type": "number", "default": 2},
        "name": {"type": "string"},
    }

    resolved = cli_app._prompt_for_inputs(cli_app.console, input_schema, {"name": "Ada"})

    assert resolved["flag"] is False
    assert resolved["choice"] == "b"
    assert resolved["items"] == ["1", "2", "3"]
    assert resolved["config"] == {"x": 1}
    assert resolved["count"] == 5
    assert resolved["name"] == "Bob"


def test_prompt_for_inputs_enum_value_and_defaults(monkeypatch):
    responses = [
        "x",  # invalid enum choice
        "blue",  # direct enum value
        '["a"]',  # array json
        '{"mode": "on"}',  # object json
    ]

    def fake_prompt(*_args, **_kwargs):
        return responses.pop(0)

    monkeypatch.setattr(cli_app.Prompt, "ask", fake_prompt)
    monkeypatch.setattr(cli_app.Confirm, "ask", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(cli_app.console, "print", lambda *_args, **_kwargs: None)

    input_schema = {
        "flag": {"type": "boolean"},
        "choice": {"enum": ["red", "blue"], "default": "red"},
        "items": {"type": "array", "default": "1,2"},
        "config": {"type": "object", "default": "key=value"},
    }

    resolved = cli_app._prompt_for_inputs(cli_app.console, input_schema, {})

    assert resolved["flag"] is True
    assert resolved["choice"] == "blue"
    assert resolved["items"] == ["a"]
    assert resolved["config"] == {"mode": "on"}
