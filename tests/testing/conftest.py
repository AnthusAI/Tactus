"""
Pytest configuration for testing tests.

This module provides fixtures for tests that use Behave, which has a global
step registry that can cause conflicts between tests.
"""

import pytest
import sys


@pytest.fixture(autouse=True, scope="function")
def clear_behave_state(request):
    """
    Clear Behave's global state before and after tests that use Behave.

    Only clears for tests in test_e2e.py that actually use Behave/TactusTestRunner.
    """
    # Clear before test if it's a Behave test
    if "test_e2e" in request.node.nodeid:
        try:
            from behave import step_registry

            step_registry.registry = step_registry.StepRegistry()
            modules_to_clear = [m for m in list(sys.modules.keys()) if "tactus_steps_" in m]
            for mod in modules_to_clear:
                del sys.modules[mod]
        except ImportError:
            pass

    yield  # Run the test

    # Clear after test if it's a Behave test
    if "test_e2e" in request.node.nodeid:
        try:
            from behave import step_registry

            step_registry.registry = step_registry.StepRegistry()
            modules_to_clear = [m for m in list(sys.modules.keys()) if "tactus_steps_" in m]
            for mod in modules_to_clear:
                del sys.modules[mod]
        except ImportError:
            pass
