"""
Comprehensive test suite for all example .tac files.

This module automatically discovers and tests all .tac files in the examples/ directory.
Each example is validated and, if it contains BDD specifications, its tests are executed.
"""

import pytest
from pathlib import Path
from typing import List, Dict, Any
import os
import re
import sys

from tactus.testing.test_runner import TactusTestRunner
from tactus.validation import TactusValidator


def should_skip_example(file_path: Path) -> bool:
    """Determine if an example should be skipped."""
    # Skip examples that require external dependencies
    if "with_dependencies" in str(file_path):
        return True

    # Skip helper procedures (not meant to run standalone)
    if "helpers" in str(file_path):
        return True

    return False


def check_for_specifications(file_path: Path) -> bool:
    """Check if a .tac file contains BDD specifications."""
    try:
        content = file_path.read_text()
        # Look for Specification( / Specifications( block
        return "Specifications(" in content or "Specification(" in content
    except Exception:
        return False


def check_requires_mcp(file_path: Path) -> bool:
    """Check if an example requires MCP servers."""
    return "mcp" in file_path.stem.lower()


def check_requires_real_api(file_path: Path) -> bool:
    """Check if an example requires real API calls (not mockable)."""
    # Examples that explicitly test real providers
    if any(provider in file_path.stem.lower() for provider in ["bedrock", "gemini", "openai"]):
        # But allow basic examples to be mocked
        if "basics" in str(file_path):
            return False
        return True
    return False


def check_uses_agents(file_path: Path) -> bool:
    """Check if an example uses agents."""
    try:
        content = file_path.read_text()
        # Look for Agent declarations
        return "Agent {" in content or "Agent{" in content
    except Exception:
        return False


def check_has_agent_mocks(file_path: Path) -> bool:
    """Check if an example has Mocks {} block with agent mock configs.

    Agent mocks are identified by having 'tool_calls' in the mock definition.
    Examples with agent mocks can run in CI without real LLM calls.
    """
    try:
        content = file_path.read_text()
        # Must have Mocks block and tool_calls (indicates agent mock)
        return "Mocks {" in content and "tool_calls" in content
    except Exception:
        return False


def categorize_example(file_path: Path) -> str:
    """Categorize an example based on its name and path."""
    stem = file_path.stem.lower()

    # Extract category from filename pattern (e.g., "01-basics-hello-world" -> "basics")
    match = re.match(r"\d+-([^-]+)", stem)
    if match:
        return match.group(1)

    # Fallback categorization
    if "eval" in stem:
        return "evaluation"
    elif "model" in stem:
        return "model"
    elif "mcp" in stem:
        return "mcp"
    elif "checkpoint" in stem:
        return "checkpoint"
    elif "file" in stem and "io" in stem:
        return "file_io"

    return "misc"


def collect_example_test_cases() -> List[Dict[str, Any]]:
    """Collect all example .tac files for testing."""
    examples_dir = Path("examples")
    test_cases = []

    if not examples_dir.exists():
        return test_cases

    for tac_file in sorted(examples_dir.glob("**/*.tac")):
        # Skip directories and certain patterns
        if tac_file.is_dir() or should_skip_example(tac_file):
            continue

        # Categorize the example
        category = categorize_example(tac_file)
        has_specs = check_for_specifications(tac_file)
        requires_mcp = check_requires_mcp(tac_file)
        requires_real_api = check_requires_real_api(tac_file)
        uses_agents = check_uses_agents(tac_file)
        has_agent_mocks = check_has_agent_mocks(tac_file)

        test_cases.append(
            {
                "file": tac_file,
                "category": category,
                "has_specs": has_specs,
                "requires_mcp": requires_mcp,
                "requires_real_api": requires_real_api,
                "uses_agents": uses_agents,
                "has_agent_mocks": has_agent_mocks,
                "id": tac_file.stem,  # For test identification
            }
        )

    return test_cases


# Collect test cases once at module load
TEST_CASES = collect_example_test_cases()


def get_mcp_servers_for_example(example: Dict[str, Any]) -> Dict[str, Any]:
    """Return MCP server configs for examples that need MCP toolsets.

    In CI we run local stdio MCP servers implemented in `tests/fixtures/`.
    """
    if not example.get("requires_mcp"):
        return {}

    example_id = example.get("id", "")
    project_root = Path(__file__).resolve().parents[2]

    if example_id in {"40-mcp-test", "41-mcp-simple"}:
        return {
            "test_server": {
                "command": sys.executable,
                "args": ["-m", "tests.fixtures.test_mcp_server"],
                "cwd": str(project_root),
            }
        }

    if example_id == "62-mcp-toolset-by-server":
        return {
            "filesystem": {
                "command": sys.executable,
                "args": ["-m", "tests.fixtures.filesystem_mcp_server"],
                "cwd": str(project_root),
            },
            "brave-search": {
                "command": sys.executable,
                "args": ["-m", "tests.fixtures.brave_search_mcp_server"],
                "cwd": str(project_root),
            },
        }

    return {}


def get_mock_tools_for_example(example: Dict[str, Any]) -> Dict[str, Any]:
    """Get appropriate mock tools for an example."""
    # Default mock tools that work for most examples
    mock_tools = {
        "done": {"status": "complete"},
        "get_time": {"time": "2024-01-01 12:00:00"},
        "calculate": {"result": 42},
        "search": {"results": ["result1", "result2"]},
        "process": {"output": "processed"},
        "validate": {"valid": True},
        "fetch": {"data": "sample data"},
        "analyze": {"analysis": "complete"},
    }

    # Add category-specific mocks
    if example["category"] == "file_io":
        mock_tools.update(
            {
                "read_file": {"content": "file content"},
                "write_file": {"success": True},
                "list_files": {"files": ["file1.txt", "file2.txt"]},
            }
        )

    return mock_tools


class TestAllExamples:
    """Test suite for all example .tac files."""

    @pytest.mark.parametrize("example", TEST_CASES, ids=lambda x: x["id"])
    def test_example_validates(self, example):
        """Test that each example file validates and loads correctly.

        This test verifies:
        1. Syntax validation passes (ANTLR parsing)
        2. Semantic validation passes (DSL structure)
        3. Lua code actually loads without runtime errors (catches undefined variables)
        """
        if not example["file"].exists():
            pytest.skip(f"Example file not found: {example['file']}")

        # Step 1: Syntax/semantic validation
        validator = TactusValidator()
        result = validator.validate_file(str(example["file"]))

        assert result.valid, f"Validation failed for {example['id']}: {result.errors}"

        # Step 2: Actually load the Lua code to catch runtime errors like undefined variables
        # This is critical - syntax validation doesn't catch undefined variables in Lua
        from tactus.core.lua_sandbox import LuaSandbox
        from tactus.core.dsl_stubs import create_dsl_stubs
        from tactus.core.registry import RegistryBuilder

        # Create sandbox with DSL stubs (like the runtime does)
        sandbox = LuaSandbox(base_path=str(example["file"].parent.resolve()))
        builder = RegistryBuilder()
        # Create DSL stubs for validation (agent creation happens during runtime setup)
        dsl_stubs = create_dsl_stubs(builder, runtime_context={})

        # Inject DSL stubs into sandbox
        lua_globals = sandbox.lua.globals()
        for name, value in dsl_stubs.items():
            if not name.startswith("_"):  # Skip internal items like _registries
                lua_globals[name] = value

        # Add strict global checking - error on undefined variable access
        # This catches issues like using 'done' without requiring it
        strict_globals_code = """
        local _defined_globals = {}
        for k, v in pairs(_G) do
            _defined_globals[k] = true
        end

        setmetatable(_G, {
            __index = function(t, k)
                if not _defined_globals[k] then
                    error("Undefined global variable: " .. tostring(k), 2)
                end
                return rawget(t, k)
            end
        })
        """
        sandbox.execute(strict_globals_code)

        # Execute the Lua code - this will fail if variables like 'done' are undefined
        source = example["file"].read_text()
        try:
            sandbox.execute(source)
        except Exception as e:
            error_msg = str(e)
            # Only fail on undefined variable errors (the purpose of this check)
            # Other errors (like agent initialization) are expected in validation mode
            # since we're not running with full runtime infrastructure
            if "Undefined global variable" in error_msg:
                pytest.fail(f"Failed to load {example['id']}: {e}")
            # Pass through for expected validation-mode errors (agent/model calls without primitives)

        # Additional checks based on category
        if example["category"] == "basics" and "agent" in example["id"]:
            assert result.registry.agents, f"Agent example {example['id']} should define agents"

    @pytest.mark.parametrize("example", TEST_CASES, ids=lambda x: x["id"])
    @pytest.mark.bdd
    @pytest.mark.xdist_group(name="behave_tests")
    def test_example_bdd_specs(self, example):
        """Test that BDD specifications pass for examples that have them."""
        if not example["has_specs"]:
            pytest.skip(f"No specifications in {example['id']}")

        if not example["file"].exists():
            pytest.skip(f"Example file not found: {example['file']}")

        # Skip if requires real API and not configured
        if example["requires_real_api"]:
            if not os.getenv("OPENAI_API_KEY") and "openai" in example["id"].lower():
                pytest.skip(f"OpenAI API key not configured for {example['id']}")
            if not os.getenv("AWS_ACCESS_KEY_ID") and "bedrock" in example["id"].lower():
                pytest.skip(f"AWS credentials not configured for {example['id']}")

        # Validate first
        validator = TactusValidator()
        result = validator.validate_file(str(example["file"]))

        assert result.valid, f"Validation failed for {example['id']}: {result.errors}"
        assert result.registry is not None
        assert result.registry.gherkin_specifications is not None

        # Setup test runner with appropriate mocking
        mock_tools = get_mock_tools_for_example(example)

        mcp_servers = get_mcp_servers_for_example(example)

        try:
            runner = TactusTestRunner(
                example["file"],
                mock_tools=mock_tools,
                mcp_servers=mcp_servers,
                tool_paths=[str(Path("examples/tools").resolve())],
                mocked=True,  # Use mock mode for all examples in CI
            )
            runner.setup(
                result.registry.gherkin_specifications,
                custom_steps_dict=result.registry.custom_steps,
            )

            # Run tests (not in parallel within test to avoid conflicts)
            test_result = runner.run_tests(parallel=False)

            # Check results
            assert test_result.total_scenarios > 0, f"No scenarios found in {example['id']}"

            assert test_result.failed_scenarios == 0, (
                f"BDD tests failed for {example['id']}: "
                f"{test_result.failed_scenarios}/{test_result.total_scenarios} scenarios failed"
            )

        finally:
            # Always cleanup
            if "runner" in locals():
                runner.cleanup()

    @pytest.mark.parametrize("example", TEST_CASES, ids=lambda x: x["id"])
    @pytest.mark.execution
    def test_example_basic_execution(self, example):
        """Track technical debt: examples without BDD specs should be SKIPPED.

        We still validate these examples so we don't silently accumulate invalid examples,
        but we deliberately mark them as skipped so it's obvious which examples still
        need `Specification([[ ... ]])` / `Specifications([[ ... ]])` coverage.
        """
        if example["has_specs"]:
            pytest.skip(f"Example {example['id']} has BDD specs, tested separately")

        if not example["file"].exists():
            pytest.skip(f"Example file not found: {example['file']}")

        # Skip examples that require special setup
        if example["requires_real_api"]:
            pytest.skip(f"Example {example['id']} requires real API calls")

        if example["requires_mcp"]:
            pytest.skip(f"Example {example['id']} requires MCP servers")

        # Validate first so invalid examples fail loudly, but then mark as skipped
        # to maintain a visible roadmap of missing specifications.
        validator = TactusValidator()
        result = validator.validate_file(str(example["file"]))

        assert result.valid, f"Validation failed for {example['id']}: {result.errors}"

        pytest.skip(
            f"Example {example['id']} has no Specification(s); add BDD specs to remove this skip"
        )


# Additional test to ensure we're testing a reasonable number of examples
def test_example_coverage():
    """Ensure we have adequate test coverage of examples."""
    assert len(TEST_CASES) > 0, "No test cases found - check examples directory"

    # We should have at least 30 examples being tested (accounting for skips)
    assert (
        len(TEST_CASES) >= 30
    ), f"Only {len(TEST_CASES)} examples found for testing, expected at least 30"

    # Check distribution of categories
    categories = {tc["category"] for tc in TEST_CASES}
    expected_categories = {"basics", "feature", "eval", "model"}

    for cat in expected_categories:
        assert cat in categories, f"Missing examples for category: {cat}"

    # Check that we have examples with BDD specs
    examples_with_specs = [tc for tc in TEST_CASES if tc["has_specs"]]
    assert (
        len(examples_with_specs) > 20
    ), f"Only {len(examples_with_specs)} examples with BDD specs, expected more"


# Mark for running specific subsets
pytest.mark.examples = pytest.mark.examples
