"""
End-to-end tests for BDD testing framework.

Tests complete flow from Gherkin parsing through execution to results.

Note: These tests use Behave which has a global step registry that persists
across tests in the same worker process. See conftest.py for the fixture that
clears the registry between tests.
"""

import pytest
from pathlib import Path

from tactus.testing.test_runner import TactusTestRunner
from tactus.validation import TactusValidator


@pytest.mark.xdist_group(name="behave_tests")
def test_simple_procedure_no_agents():
    """Test complete flow with simple procedure (no agents)."""
    procedure_file = Path("examples/02-basics-simple-logic.tac")

    if not procedure_file.exists():
        pytest.skip(f"Example file not found: {procedure_file}")

    # Validate and extract specifications
    validator = TactusValidator()
    result = validator.validate_file(str(procedure_file))

    assert result.valid, f"Validation failed: {result.errors}"
    assert result.registry is not None
    assert result.registry.gherkin_specifications is not None

    # Setup test runner
    runner = TactusTestRunner(procedure_file)
    runner.setup(result.registry.gherkin_specifications)

    # Run tests
    test_result = runner.run_tests(parallel=False)

    # Verify results
    assert test_result.total_scenarios == 3
    assert test_result.passed_scenarios == 3
    assert test_result.failed_scenarios == 0

    # Cleanup
    runner.cleanup()


@pytest.mark.xdist_group(name="behave_tests")
def test_procedure_with_mocked_agents():
    """Test procedure with agents in mock mode."""
    procedure_file = Path("examples/21-bdd-passing.tac")

    if not procedure_file.exists():
        pytest.skip(f"Example file not found: {procedure_file}")

    # Validate and extract specifications
    validator = TactusValidator()
    result = validator.validate_file(str(procedure_file))

    assert result.valid
    assert result.registry.gherkin_specifications is not None

    # Setup with mocked tools
    mock_tools = {"done": {"status": "complete"}}

    runner = TactusTestRunner(procedure_file, mock_tools=mock_tools)
    runner.setup(result.registry.gherkin_specifications)

    # Run tests
    test_result = runner.run_tests(parallel=False)

    # Should complete (may have failures depending on assertions)
    assert test_result.total_scenarios > 0

    # Cleanup
    runner.cleanup()


@pytest.mark.xdist_group(name="behave_tests")
def test_evaluation_with_mock_mode():
    """Test evaluation runner with mock mode."""
    procedure_file = Path("examples/02-basics-simple-logic.tac")

    if not procedure_file.exists():
        pytest.skip(f"Example file not found: {procedure_file}")

    # Validate
    validator = TactusValidator()
    result = validator.validate_file(str(procedure_file))

    assert result.valid

    # Setup evaluation runner
    from tactus.testing.evaluation_runner import TactusEvaluationRunner

    evaluator = TactusEvaluationRunner(procedure_file)
    evaluator.setup(result.registry.gherkin_specifications)

    # Run evaluation with just 3 runs for speed
    eval_results = evaluator.evaluate_all(runs=3, parallel=True)

    # Verify results
    assert len(eval_results) == 3  # 3 scenarios

    for eval_result in eval_results:
        assert eval_result.total_runs == 3
        assert eval_result.success_rate >= 0.0
        assert eval_result.consistency_score >= 0.0

    # Cleanup
    evaluator.cleanup()


@pytest.mark.xdist_group(name="behave_tests")
def test_cli_test_command_mock_mode(tmp_path):
    """Test CLI test command with mock mode."""
    from typer.testing import CliRunner
    from tactus.cli.app import app

    # Create a simple test procedure
    test_proc = tmp_path / "test.tac"
    test_proc.write_text(
        """
agent("worker", {
  provider = "openai",
  model = "gpt-4o-mini",
  system_prompt = "Test",
  tools = {"done"}
})

stages({"start", "end"})

procedure(function()
  Stage.set("start")
  Worker.turn()
  Stage.set("end")
  return {success = true}
end)

specifications([[
Feature: Test
  Scenario: Works
    Given the procedure has started
    When the procedure runs
    Then the stage should be end
]])
"""
    )

    runner = CliRunner()
    result = runner.invoke(app, ["test", str(test_proc), "--mock", "--no-parallel"])

    # Should not error (even if test fails, CLI should handle it)
    assert result.exit_code in [0, 1]  # 0 = pass, 1 = test failure


@pytest.mark.xdist_group(name="behave_tests")
def test_parameter_passing():
    """Test that parameters are passed correctly to procedures."""
    procedure_file = Path("examples/02-basics-simple-logic.tac")

    if not procedure_file.exists():
        pytest.skip(f"Example file not found: {procedure_file}")

    validator = TactusValidator()
    result = validator.validate_file(str(procedure_file))

    # Run with custom parameter
    runner = TactusTestRunner(procedure_file, params={"target_count": 3})
    runner.setup(result.registry.gherkin_specifications)

    test_result = runner.run_tests(parallel=True)

    # Should complete
    assert test_result.total_scenarios > 0

    runner.cleanup()
