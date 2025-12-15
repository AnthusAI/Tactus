"""
Pytest configuration for testing tests.

This module provides fixtures for tests that use Behave, which has a global
step registry that can cause conflicts between tests.
"""

import pytest
import sys
import importlib


def _clear_behave_modules():
    """
    Aggressively clear Behave-related modules from sys.modules.

    Clears:
    - Generated step files (tactus_steps_*)
    - Step modules from steps directory
    - Behave's step registry
    - All 'steps' modules (to handle different temp directories)

    IMPORTANT: We call registry.clear() instead of creating a new registry
    because the @step decorator has a closure reference to the registry object.
    If we create a new object, the decorator still uses the old one!
    """
    try:
        from behave import step_registry

        # Clear Behave's global step registry IN-PLACE
        # This is crucial - we must clear the existing object, not replace it
        step_registry.registry.clear()

        # Clear all generated step files and related modules
        # Be very aggressive - clear ANY module that looks like a steps module
        modules_to_clear = [
            m
            for m in list(sys.modules.keys())
            if any(
                [
                    "tactus_steps_" in m,
                    "steps.tactus_steps_" in m,
                    m.startswith("steps.") and "tactus" in m,
                    m == "steps",  # Clear the steps package itself
                    m.startswith("steps") and not m.startswith("steps."),  # Clear steps variants
                ]
            )
        ]

        for mod in modules_to_clear:
            try:
                del sys.modules[mod]
            except KeyError:
                pass  # Already deleted

        # Invalidate import caches to ensure fresh imports
        importlib.invalidate_caches()

    except ImportError:
        pass


@pytest.fixture(autouse=True, scope="function")
def clear_behave_state(request):
    """
    Clear Behave's global state after tests that use Behave.

    Only clears for tests in test_e2e.py that actually use Behave/TactusTestRunner.

    We clear ONLY after the test (not before) because:
    - Clearing before would make step definitions "undefined"
    - Clearing after ensures the next test starts with a clean registry

    The TactusTestRunner.cleanup() method ALSO clears the registry, but this
    fixture provides an additional safety net in case cleanup() isn't called.
    """
    yield  # Run the test first

    # Clear after test if it's a Behave test
    if "test_e2e" in request.node.nodeid:
        _clear_behave_modules()
