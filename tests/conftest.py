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
