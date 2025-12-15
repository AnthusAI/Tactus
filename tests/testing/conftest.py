"""
Pytest configuration for testing tests.

This module provides fixtures for tests that use Behave, which has a global
step registry that can cause conflicts between tests.
"""

import pytest
import sys


@pytest.fixture(autouse=True, scope="function")
def clear_behave_state():
    """
    Clear Behave's global state before and after each test.

    Behave uses a global step registry that persists across tests when
    running in the same process. This fixture clears the registry both
    BEFORE and AFTER each test to prevent pollution.
    """
    # Clear before test starts
    try:
        from behave import step_registry

        step_registry.registry = step_registry.StepRegistry()
        modules_to_clear = [m for m in list(sys.modules.keys()) if "tactus_steps_" in m]
        for mod in modules_to_clear:
            del sys.modules[mod]
    except ImportError:
        # Behave not installed, skip cleanup
        pass

    yield  # Run the test

    # Clear after test completes
    try:
        from behave import step_registry

        step_registry.registry = step_registry.StepRegistry()
        modules_to_clear = [m for m in list(sys.modules.keys()) if "tactus_steps_" in m]
        for mod in modules_to_clear:
            del sys.modules[mod]
    except ImportError:
        # Behave not installed, skip cleanup
        pass
