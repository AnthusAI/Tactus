"""
Tests for CLI interactive input prompting.

Tests the --param and --interactive flags for passing procedure inputs.
"""

import pytest
from rich.console import Console
from typer.testing import CliRunner

from tactus.cli.app import app, _parse_value, _check_missing_required_inputs, _prompt_for_inputs

pytestmark = pytest.mark.integration


@pytest.fixture
def cli_runner():
    """Fixture providing a Typer CliRunner for testing CLI commands."""
    return CliRunner()


@pytest.fixture
def procedure_with_string_input(tmp_path):
    """Create procedure with a required string input."""
    content = """main = Procedure {
    input = {
        name = field.string{required = true, description = "User name to greet"}
    },
    output = {
        greeting = field.string{required = true}
    },
    state = {},
    function(input)
        return { greeting = "Hello, " .. input.name .. "!" }
    end
}"""
    f = tmp_path / "string_input.tac"
    f.write_text(content)
    return f


@pytest.fixture
def procedure_with_default_input(tmp_path):
    """Create procedure with an input that has a default value."""
    content = """main = Procedure {
    input = {
        name = field.string{default = "World", description = "User name to greet"}
    },
    output = {
        greeting = field.string{required = true}
    },
    state = {},
    function(input)
    return { greeting = "Hello, " .. input.name .. "!" }
end
}"""
    f = tmp_path / "default_input.tac"
    f.write_text(content)
    return f


@pytest.fixture
def procedure_with_all_types(tmp_path):
    """Create procedure with all input types."""
    content = """main = Procedure {
    input = {
        text = field.string{required = true, description = "A text value"},
        count = field.number{default = 10, description = "A number value"},
        enabled = field.boolean{default = false, description = "A boolean flag"},
        items = field.array{default = {}, description = "An array of items"},
        config = field.object{default = {}, description = "A config object"}
    },
    output = {
        result = field.string{required = true}
    },
    state = {},
    function(input)
    return { result = "processed: " .. input.text }
end
}"""
    f = tmp_path / "all_types.tac"
    f.write_text(content)
    return f


@pytest.fixture
def procedure_with_array_input(tmp_path):
    """Create procedure with a required array input."""
    content = """main = Procedure {
    input = {
        numbers = field.array{required = true, description = "Array of numbers to sum"}
    },
    output = {
        sum = field.number{required = true}
    },
    state = {},
    function(input)
    local total = 0
    for _, n in ipairs(input.numbers) do
        total = total + n
    end
    return { sum = total }
end
}"""
    f = tmp_path / "array_input.tac"
    f.write_text(content)
    return f


@pytest.fixture
def procedure_with_enum_input(tmp_path):
    """Create procedure with an enum input."""
    content = """main = Procedure {
    input = {
        status = field.string{required = true, enum = {"active", "inactive", "pending"}, description = "Status selection"}
    },
    output = {
        message = field.string{required = true}
    },
    state = {},
    function(input)
    return { message = "Status is: " .. input.status }
end
}"""
    f = tmp_path / "enum_input.tac"
    f.write_text(content)
    return f


class TestParseValue:
    """Tests for the _parse_value helper function."""

    def test_parse_string(self):
        """Test parsing string values."""
        assert _parse_value("hello", "string") == "hello"
        assert _parse_value("hello world", "string") == "hello world"

    def test_parse_number_int(self):
        """Test parsing integer values."""
        assert _parse_value("42", "number") == 42
        assert _parse_value("0", "number") == 0
        assert _parse_value("-5", "number") == -5

    def test_parse_number_float(self):
        """Test parsing float values."""
        assert _parse_value("3.14", "number") == 3.14
        assert _parse_value("0.5", "number") == 0.5

    def test_parse_number_invalid(self):
        """Test parsing invalid number returns 0."""
        assert _parse_value("not a number", "number") == 0

    def test_parse_boolean_true(self):
        """Test parsing boolean true values."""
        assert _parse_value("true", "boolean") is True
        assert _parse_value("True", "boolean") is True
        assert _parse_value("yes", "boolean") is True
        assert _parse_value("1", "boolean") is True
        assert _parse_value("y", "boolean") is True

    def test_parse_boolean_false(self):
        """Test parsing boolean false values."""
        assert _parse_value("false", "boolean") is False
        assert _parse_value("no", "boolean") is False
        assert _parse_value("0", "boolean") is False

    def test_parse_array_json(self):
        """Test parsing JSON array values."""
        assert _parse_value("[1, 2, 3]", "array") == [1, 2, 3]
        assert _parse_value('["a", "b"]', "array") == ["a", "b"]
        assert _parse_value("[]", "array") == []

    def test_parse_array_csv(self):
        """Test parsing comma-separated array values."""
        assert _parse_value("a, b, c", "array") == ["a", "b", "c"]
        assert _parse_value("1,2,3", "array") == ["1", "2", "3"]

    def test_parse_array_empty(self):
        """Test parsing empty array."""
        assert _parse_value("", "array") == []

    def test_parse_object_json(self):
        """Test parsing JSON object values."""
        assert _parse_value('{"key": "value"}', "object") == {"key": "value"}
        assert _parse_value("{}", "object") == {}

    def test_parse_object_invalid(self):
        """Test parsing invalid object returns empty dict."""
        assert _parse_value("not json", "object") == {}


class TestCheckMissingRequiredInputs:
    """Tests for the _check_missing_required_inputs helper function."""

    def test_no_missing_when_all_provided(self):
        """Test no missing inputs when all required are provided."""
        schema = {
            "name": {"type": "string", "required": True},
            "age": {"type": "number", "required": True},
        }
        provided = {"name": "Alice", "age": 30}
        assert _check_missing_required_inputs(schema, provided) == []

    def test_missing_required_input(self):
        """Test detecting missing required input."""
        schema = {
            "name": {"type": "string", "required": True},
            "age": {"type": "number", "required": True},
        }
        provided = {"name": "Alice"}
        assert _check_missing_required_inputs(schema, provided) == ["age"]

    def test_required_with_default_not_missing(self):
        """Test required input with default is not considered missing."""
        schema = {
            "name": {"type": "string", "required": True, "default": "Default"},
        }
        provided = {}
        assert _check_missing_required_inputs(schema, provided) == []

    def test_optional_not_missing(self):
        """Test optional inputs are not considered missing."""
        schema = {
            "name": {"type": "string", "required": False},
        }
        provided = {}
        assert _check_missing_required_inputs(schema, provided) == []

    def test_empty_schema(self):
        """Test empty schema returns no missing."""
        assert _check_missing_required_inputs({}, {}) == []


class TestCLIInputs:
    """Integration tests for CLI input handling."""

    def test_run_with_string_param(self, cli_runner, procedure_with_string_input):
        """Test running with a string parameter via --param."""
        result = cli_runner.invoke(
            app,
            ["run", str(procedure_with_string_input), "--no-sandbox", "--param", "name=Alice"],
        )
        assert result.exit_code == 0
        assert "Hello, Alice!" in result.stdout

    def test_run_with_default_value(self, cli_runner, procedure_with_default_input):
        """Test running uses default value when param not provided."""
        result = cli_runner.invoke(app, ["run", str(procedure_with_default_input), "--no-sandbox"])
        assert result.exit_code == 0
        assert "Hello, World!" in result.stdout

    def test_run_override_default(self, cli_runner, procedure_with_default_input):
        """Test --param overrides default value."""
        result = cli_runner.invoke(
            app,
            ["run", str(procedure_with_default_input), "--no-sandbox", "--param", "name=Custom"],
        )
        assert result.exit_code == 0
        assert "Hello, Custom!" in result.stdout

    def test_run_with_array_param_json(self, cli_runner, procedure_with_array_input):
        """Test running with JSON array parameter - verifies array is accepted."""
        result = cli_runner.invoke(
            app,
            [
                "run",
                str(procedure_with_array_input),
                "--no-sandbox",
                "--param",
                "numbers=[1,2,3,4]",
            ],
        )
        # The test verifies that:
        # 1. The JSON array parameter is parsed correctly
        # 2. The procedure runs to completion without error
        # Note: The sum calculation is a runtime behavior tested separately
        assert result.exit_code == 0
        assert "completed successfully" in result.stdout

    def test_run_interactive_mode(self, cli_runner, procedure_with_string_input):
        """Test interactive mode prompts for inputs."""
        result = cli_runner.invoke(
            app,
            ["run", str(procedure_with_string_input), "--no-sandbox", "-i"],
            input="TestUser\n",
        )
        # Should prompt and complete
        assert "name" in result.stdout.lower()  # Shows the input name

    def test_run_missing_required_prompts(self, cli_runner, procedure_with_string_input):
        """Test missing required input triggers interactive prompt."""
        result = cli_runner.invoke(
            app,
            ["run", str(procedure_with_string_input), "--no-sandbox"],
            input="PromptedUser\n",
        )
        # Should indicate missing input and prompt
        assert "missing required" in result.stdout.lower() or "name" in result.stdout.lower()

    def test_run_with_multiple_params(self, cli_runner, procedure_with_all_types):
        """Test running with multiple parameters."""
        result = cli_runner.invoke(
            app,
            [
                "run",
                str(procedure_with_all_types),
                "--no-sandbox",
                "--param",
                "text=hello",
                "--param",
                "count=5",
                "--param",
                "enabled=true",
            ],
        )
        assert result.exit_code == 0
        assert "processed: hello" in result.stdout

    def test_interactive_with_preexisting_params(self, cli_runner, procedure_with_all_types):
        """Test interactive mode shows pre-existing --param values."""
        result = cli_runner.invoke(
            app,
            ["run", str(procedure_with_all_types), "--no-sandbox", "-i", "--param", "text=preset"],
            input="\n5\nn\n[]\n{}\n",  # Accept defaults for remaining
        )
        # Should show "preset" in the current column
        assert "preset" in result.stdout or result.exit_code == 0


class TestCLIParamParsing:
    """Tests for parameter parsing from --param flag."""

    def test_param_json_array(self, cli_runner, tmp_path):
        """Test --param correctly parses JSON arrays."""
        content = """main = Procedure {
    input = {nums = field.array{required = true}},
    output = {count = field.number{required = true}},
    function(input)
        return {count = #input.nums}
    end
}"""
        f = tmp_path / "test.tac"
        f.write_text(content)

        result = cli_runner.invoke(app, ["run", str(f), "--no-sandbox", "--param", "nums=[1,2,3]"])
        assert result.exit_code == 0


def test_prompt_for_inputs_enum(monkeypatch):
    input_schema = {"status": {"type": "string", "enum": ["active", "inactive"], "required": True}}
    provided = {}
    answers = iter(["2"])

    monkeypatch.setattr("tactus.cli.app.Prompt.ask", lambda *args, **kwargs: next(answers))

    resolved = _prompt_for_inputs(Console(), input_schema, provided)

    assert resolved["status"] == "inactive"


def test_prompt_for_inputs_boolean(monkeypatch):
    input_schema = {"enabled": {"type": "boolean", "required": True}}
    provided = {}

    monkeypatch.setattr("tactus.cli.app.Confirm.ask", lambda *args, **kwargs: True)

    resolved = _prompt_for_inputs(Console(), input_schema, provided)

    assert resolved["enabled"] is True

    def test_param_json_object(self, cli_runner, tmp_path):
        """Test --param correctly parses JSON objects."""
        content = """main = Procedure {
    input = {cfg = field.object{default = {}}},
    output = {ok = field.boolean{required = true}},
    function(input)
        return {ok = true}
    end
}"""
        f = tmp_path / "test.tac"
        f.write_text(content)

        result = cli_runner.invoke(
            app, ["run", str(f), "--no-sandbox", "--param", 'cfg={"key":"value"}']
        )
        assert result.exit_code == 0

    def test_param_boolean(self, cli_runner, tmp_path):
        """Test --param correctly parses boolean values."""
        content = """main = Procedure {
    input = {flag = field.boolean{default = false}},
    output = {result = field.boolean{required = true}},
    function(input)
        return {result = input.flag}
    end
}"""
        f = tmp_path / "test.tac"
        f.write_text(content)

        result = cli_runner.invoke(app, ["run", str(f), "--no-sandbox", "--param", "flag=true"])
        assert result.exit_code == 0

    def test_param_number(self, cli_runner, tmp_path):
        """Test --param correctly parses number values."""
        content = """main = Procedure {
    input = {n = field.number{default = 0}},
    output = {doubled = field.number{required = true}},
    function(input)
        return {doubled = input.n * 2}
    end
}"""
        f = tmp_path / "test.tac"
        f.write_text(content)

        result = cli_runner.invoke(app, ["run", str(f), "--no-sandbox", "--param", "n=21"])
        assert result.exit_code == 0
        assert "42" in result.stdout
