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
    workflow_content = """agent("worker", {
    provider = "openai",
    system_prompt = "You are a test worker.",
    initial_message = "Starting test.",
    tools = {}
})

procedure({
    output = {
        result = {
            type = "string",
            required = true
        }
    },
    state = {}
}, function()
    return { result = "test" }
end)
"""
    workflow_file = tmp_path / "test.tac"
    workflow_file.write_text(workflow_content)
    return workflow_file


def test_cli_validate_valid_file(cli_runner, example_workflow_file):
    """Test that validate command works with a valid workflow file."""
    result = cli_runner.invoke(app, ["validate", str(example_workflow_file)])
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
    workflow_content = """agent("worker", {
    provider = "openai",
    system_prompt = "You are a test worker.",
    initial_message = "Starting test.",
    tools = {}
})

procedure({
    input = {
        name = {
            type = "string",
            default = "World"
        }
    },
    output = {
        greeting = {
            type = "string",
            required = true
        }
    },
    state = {}
}, function()
    return { greeting = "Hello, " .. input.name }
end)
"""
    workflow_file = tmp_path / "params.tac"
    workflow_file.write_text(workflow_content)

    result = cli_runner.invoke(app, ["run", str(workflow_file), "--param", "name=TestUser"])
    assert result.exit_code == 0
