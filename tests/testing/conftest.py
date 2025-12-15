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
    Clear Behave's global state after tests that use Behave.

    Only clears for tests in test_e2e.py that actually use Behave/TactusTestRunner.
    This prevents clearing the registry while Behave is actively using it.
    """
    yield  # Run the test first

    # Only clear after tests that use Behave (test_e2e.py tests)
    if "test_e2e" in request.node.nodeid:
        try:
            from behave import step_registry

            step_registry.registry = step_registry.StepRegistry()
            modules_to_clear = [m for m in list(sys.modules.keys()) if "tactus_steps_" in m]
            for mod in modules_to_clear:
                del sys.modules[mod]
        except ImportError:
            # Behave not installed, skip cleanup
            pass
