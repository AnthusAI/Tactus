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
    workflow_content = """name: test_workflow
version: 1.0.0
agents:
  worker:
    provider: openai
    system_prompt: "You are a test worker."
    initial_message: "Starting test."
procedure: |
  return { result = "test" }
outputs:
  result:
    type: string
    required: true
"""
    workflow_file = tmp_path / "test.tyml"
    workflow_file.write_text(workflow_content)
    return workflow_file


def test_cli_validate_valid_file(cli_runner, example_workflow_file):
    """Test that validate command works with a valid workflow file."""
    result = cli_runner.invoke(app, ["validate", str(example_workflow_file)])
    assert result.exit_code == 0
    assert "YAML is valid" in result.stdout
    assert "test_workflow" in result.stdout


def test_cli_validate_missing_file(cli_runner):
    """Test that validate command handles missing files gracefully."""
    result = cli_runner.invoke(app, ["validate", "nonexistent.tyml"])
    assert result.exit_code == 1
    assert "not found" in result.stdout.lower()


def test_cli_validate_invalid_yaml(cli_runner, tmp_path):
    """Test that validate command handles invalid YAML gracefully."""
    invalid_file = tmp_path / "invalid.tyml"
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
    result = cli_runner.invoke(app, ["run", "nonexistent.tyml"])
    assert result.exit_code == 1
    assert "not found" in result.stdout.lower()


def test_cli_version(cli_runner):
    """Test that version command works."""
    result = cli_runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "Tactus version" in result.stdout
    assert "0.1.0" in result.stdout


def test_cli_run_with_parameters(cli_runner, tmp_path):
    """Test that run command accepts parameters."""
    workflow_content = """name: test_params
version: 1.0.0
params:
  name:
    type: string
    default: "World"
agents:
  worker:
    provider: openai
    system_prompt: "You are a test worker."
    initial_message: "Starting test."
procedure: |
  return { greeting = "Hello, " .. params.name }
outputs:
  greeting:
    type: string
    required: true
"""
    workflow_file = tmp_path / "params.tyml"
    workflow_file.write_text(workflow_content)

    result = cli_runner.invoke(app, ["run", str(workflow_file), "--param", "name=TestUser"])
    assert result.exit_code == 0
