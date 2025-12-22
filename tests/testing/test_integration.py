"""
Integration tests for BDD testing framework.
"""

from pathlib import Path
import tempfile

from tactus.testing.gherkin_parser import GherkinParser
from tactus.testing.behave_integration import setup_behave_directory
from tactus.testing.steps.registry import StepRegistry
from tactus.testing.steps.builtin import register_builtin_steps
from tactus.testing.steps.custom import CustomStepManager


def test_full_integration_setup():
    """Test complete setup of Behave directory."""
    gherkin_text = """
Feature: Test Feature

  Scenario: Test Scenario
    Given the procedure has started
    When the procedure runs
    Then the procedure should complete successfully
"""

    # Parse Gherkin
    parser = GherkinParser()
    parsed_feature = parser.parse(gherkin_text)

    # Setup step registry
    registry = StepRegistry()
    register_builtin_steps(registry)

    # Setup custom steps
    custom_steps = CustomStepManager()

    # Create temp procedure file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".lua", delete=False) as f:
        f.write("-- test procedure")
        procedure_file = Path(f.name)

    try:
        # Setup Behave directory
        work_dir = setup_behave_directory(
            parsed_feature,
            registry,
            custom_steps,
            procedure_file,
        )

        # Verify directory structure
        assert work_dir.exists()
        assert (work_dir / "test_feature.feature").exists()
        assert (work_dir / "steps").exists()
        # Check for any tactus_steps_*.py file (name includes hash now)
        step_files = list((work_dir / "steps").glob("tactus_steps_*.py"))
        assert len(step_files) > 0, "No tactus_steps_*.py file found"
        assert (work_dir / "environment.py").exists()

        # Verify feature file content
        feature_content = (work_dir / "test_feature.feature").read_text()
        assert "Feature: Test Feature" in feature_content
        assert "Scenario: Test Scenario" in feature_content
        assert "Given the procedure has started" in feature_content

        # Cleanup
        import shutil

        shutil.rmtree(work_dir)

    finally:
        procedure_file.unlink()


def test_step_registry_with_builtin_steps():
    """Test that built-in steps are registered correctly."""
    registry = StepRegistry()
    register_builtin_steps(registry)

    # Test tool step matching
    func, match_dict = registry.match("the search tool should be called")
    assert func is not None
    assert match_dict.get("tool") == "search"

    # Test stage step matching
    func, match_dict = registry.match("the stage should be processing")
    assert func is not None
    assert match_dict.get("stage") == "processing"

    # Test iteration step matching
    func, match_dict = registry.match("the total iterations should be less than 10")
    assert func is not None
    assert match_dict.get("n") == "10"


def test_custom_step_manager():
    """Test custom step manager."""
    manager = CustomStepManager()

    # Register a custom step
    def my_custom_step(context):
        context.custom_executed = True

    manager.register_from_lua("my custom step", my_custom_step)

    # Check it's registered
    assert manager.has_step("my custom step")
    assert "my custom step" in manager.get_all_steps()

    # Execute it
    class MockContext:
        pass

    context = MockContext()
    executed = manager.execute("my custom step", context)

    assert executed is True
    assert context.custom_executed is True
