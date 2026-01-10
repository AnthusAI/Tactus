"""
CLI smoke tests for Tactus command-line interface.

Tests basic CLI functionality using Typer's CliRunner to ensure
commands work correctly and handle errors gracefully.
"""

import pytest
from typer.testing import CliRunner

from tactus.cli.app import app

pytestmark = pytest.mark.integration


@pytest.fixture
def cli_runner():
    """Fixture providing a Typer CliRunner for testing CLI commands."""
    return CliRunner()


@pytest.fixture
def example_workflow_file(tmp_path):
    """Create a minimal valid workflow file for testing."""
    workflow_content = """worker = Agent {
    provider = "openai",
    system_message = "You are a test worker.",
    message = "Starting test.",
    tools = {}
}

output {
    result = field.string{required = true}
}

return { result = "test" }
"""
    workflow_file = tmp_path / "test.tac"
    workflow_file.write_text(workflow_content)
    return workflow_file


def test_cli_validate_valid_file(cli_runner, example_workflow_file):
    """Test that validate command works with a valid workflow file."""
    result = cli_runner.invoke(app, ["validate", str(example_workflow_file)])
    if result.exit_code != 0:
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr if hasattr(result, 'stderr') else 'N/A'}")
    assert result.exit_code == 0
    assert "valid" in result.stdout.lower()


def test_cli_validate_missing_file(cli_runner):
    """Test that validate command handles missing files gracefully."""
    result = cli_runner.invoke(app, ["validate", "nonexistent.tac"])
    assert result.exit_code == 1
    assert "not found" in result.stdout.lower()


def test_cli_validate_invalid_yaml(cli_runner, tmp_path):
    """Test that validate command handles invalid YAML gracefully."""
    invalid_file = tmp_path / "invalid.tac"
    invalid_file.write_text("invalid: yaml: content: [")

    result = cli_runner.invoke(app, ["validate", str(invalid_file)])
    assert result.exit_code == 1
    assert "error" in result.stdout.lower() or "invalid" in result.stdout.lower()


def test_cli_run_valid_file(cli_runner, example_workflow_file):
    """Test that run command executes a valid workflow file."""
    result = cli_runner.invoke(app, ["run", str(example_workflow_file)])
    # Should succeed (exit code 0) for a simple workflow
    assert result.exit_code == 0
    assert "completed successfully" in result.stdout.lower() or "result" in result.stdout.lower()


def test_cli_run_missing_file(cli_runner):
    """Test that run command handles missing files gracefully."""
    result = cli_runner.invoke(app, ["run", "nonexistent.tac"])
    assert result.exit_code == 1
    assert "not found" in result.stdout.lower()


def test_cli_version(cli_runner):
    """Test that version command works."""
    result = cli_runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "Tactus version" in result.stdout
    # Check for version number (could be 0.1.0, 0.2.1, etc.)
    assert "Tactus version" in result.stdout


def test_cli_run_with_parameters(cli_runner, tmp_path):
    """Test that run command accepts parameters."""
    workflow_content = """worker = Agent {
    provider = "openai",
    system_message = "You are a test worker.",
    message = "Starting test.",
    tools = {}
}

Procedure {
    input = {
        name = field.string{default = "World"}
    },
    output = {
        greeting = field.string{required = true}
    },
    function(input)
        return { greeting = "Hello, " .. input.name }
    end
}
"""
    workflow_file = tmp_path / "params.tac"
    workflow_file.write_text(workflow_content)

    result = cli_runner.invoke(app, ["run", str(workflow_file), "--param", "name=TestUser"])
    assert result.exit_code == 0
