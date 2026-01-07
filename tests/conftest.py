"""
Root pytest configuration for Tactus tests.

Provides global fixtures and configuration for all tests.
"""

import pytest
import os
from pathlib import Path


def pytest_configure(config):
    """
    Load Tactus configuration and export API keys to environment.

    This runs BEFORE test collection, so skipif conditions can see the environment variables.
    """
    import yaml

    # Find the project root (where .tactus/config.yml is located)
    project_root = Path(__file__).parent.parent
    config_file = project_root / ".tactus" / "config.yml"

    if not config_file.exists():
        # No config file, skip loading
        return

    # Load configuration directly from YAML
    with open(config_file) as f:
        tactus_config = yaml.safe_load(f) or {}

    # Export config values as environment variables (matching ConfigManager's env_mappings)
    env_mappings = {
        "openai_api_key": "OPENAI_API_KEY",
        "google_api_key": "GOOGLE_API_KEY",
        ("aws", "access_key_id"): "AWS_ACCESS_KEY_ID",
        ("aws", "secret_access_key"): "AWS_SECRET_ACCESS_KEY",
        ("aws", "default_region"): "AWS_DEFAULT_REGION",
    }

    for config_key, env_key in env_mappings.items():
        # Skip if environment variable is already set
        if env_key in os.environ:
            continue

        # Get value from config
        if isinstance(config_key, tuple):
            # Nested key (e.g., aws.access_key_id)
            value = tactus_config.get(config_key[0], {}).get(config_key[1])
        else:
            value = tactus_config.get(config_key)

        # Set environment variable if value exists
        if value:
            os.environ[env_key] = str(value)


def pytest_addoption(parser):
    """Add custom pytest command-line options."""
    parser.addoption(
        "--real-api",
        action="store_true",
        default=False,
        help="Run tests against real APIs instead of mocks (requires API keys)",
    )


@pytest.fixture(scope="session")
def use_real_api(request):
    """Fixture that returns whether to use real APIs."""
    return request.config.getoption("--real-api")


@pytest.fixture
def setup_llm_mocks(use_real_api, request):
    """
    Set up LLM mocks unless --real-api is set.

    This fixture must be explicitly requested by tests that need mocking.
    NOT autouse to avoid hanging pytest.
    """
    if not use_real_api:
        # Import mock system
        from tests.mocks.llm_mocks import setup_default_mocks, clear_mock_providers

        # Set up default mocks for common models
        setup_default_mocks()

        # Register cleanup
        def cleanup():
            clear_mock_providers()

        request.addfinalizer(cleanup)
    else:
        # When using real API, verify credentials are available
        if not os.environ.get("OPENAI_API_KEY"):
            pytest.skip("--real-api specified but OPENAI_API_KEY not set")


@pytest.fixture
def mock_llm_provider(use_real_api):
    """
    Fixture that provides access to mock LLM providers.

    Only available when not using real API.
    """
    if use_real_api:
        pytest.skip("Mock providers not available when using --real-api")

    from tests.mocks.llm_mocks import MockLLMProvider, register_mock_provider, get_mock_provider

    return {"create": MockLLMProvider, "register": register_mock_provider, "get": get_mock_provider}


@pytest.fixture
def setup_example_test_environment(tmp_path, request):
    """
    Set up test environment for example .tac files.

    This fixture:
    - Creates temporary directories for file I/O examples
    - Sets up mock LLM providers
    - Configures test-specific environment variables
    """
    # Create temp directories for file operations
    test_data_dir = tmp_path / "test_data"
    test_data_dir.mkdir(exist_ok=True)

    # Set environment variables for testing
    original_env = {}
    test_env_vars = {
        "TACTUS_TEST_MODE": "true",
        "TACTUS_TEST_DATA_DIR": str(test_data_dir),
    }

    for key, value in test_env_vars.items():
        original_env[key] = os.environ.get(key)
        os.environ[key] = value

    # Setup mock LLM providers if not using real API
    if not request.config.getoption("--real-api"):
        from tests.mocks.llm_mocks import setup_default_mocks, clear_mock_providers

        setup_default_mocks()

    yield test_data_dir

    # Cleanup
    for key, original_value in original_env.items():
        if original_value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = original_value

    # Clear mock providers if they were set up
    if not request.config.getoption("--real-api"):
        clear_mock_providers()


@pytest.fixture
def mock_mcp_server():
    """
    Mock MCP server for testing MCP-related examples.

    Provides a mock server that responds to tool discovery and execution.
    """

    class MockMCPServer:
        def __init__(self):
            self.tools = {
                "example_tool": {
                    "name": "example_tool",
                    "description": "An example MCP tool",
                    "input": {"input": "string"},
                }
            }
            self.call_count = 0

        def discover_tools(self):
            """Return available tools."""
            return list(self.tools.values())

        def execute_tool(self, tool_name, parameters):
            """Execute a tool and return result."""
            self.call_count += 1
            if tool_name in self.tools:
                return {
                    "success": True,
                    "result": f"Executed {tool_name}",
                    "count": self.call_count,
                }
            return {"success": False, "error": f"Unknown tool: {tool_name}"}

        def reset(self):
            """Reset the server state."""
            self.call_count = 0

    return MockMCPServer()


@pytest.fixture
def example_test_data(tmp_path):
    """
    Create test data files for file I/O examples.

    Creates various file formats with sample data.
    """
    # Create sample CSV file
    csv_file = tmp_path / "sample.csv"
    csv_file.write_text("name,age,city\nAlice,30,NYC\nBob,25,LA\nCharlie,35,Chicago\n")

    # Create sample JSON file
    json_file = tmp_path / "sample.json"
    import json

    json_data = {
        "users": [
            {"id": 1, "name": "Alice", "active": True},
            {"id": 2, "name": "Bob", "active": False},
        ],
        "metadata": {"version": "1.0", "created": "2024-01-01"},
    }
    json_file.write_text(json.dumps(json_data, indent=2))

    # Create sample text file
    text_file = tmp_path / "sample.txt"
    text_file.write_text(
        "This is a sample text file.\nIt has multiple lines.\nFor testing purposes.\n"
    )

    # Create sample TSV file
    tsv_file = tmp_path / "sample.tsv"
    tsv_file.write_text("id\tname\tvalue\n1\tItem1\t100\n2\tItem2\t200\n3\tItem3\t300\n")

    return {"csv": csv_file, "json": json_file, "text": text_file, "tsv": tsv_file, "dir": tmp_path}
