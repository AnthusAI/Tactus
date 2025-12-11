"""
Root pytest configuration for Tactus tests.

Provides global fixtures and configuration for all tests.
"""

import pytest
import os


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
