"""
Behave environment configuration for Tactus end‑to‑end tests.

Provides light-weight fixtures commonly used across the feature files
so individual step definitions can focus on behavior instead of setup
and teardown plumbing.
"""

from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path


def before_all(context):
    """Run once before all tests."""
    context.config.setup_logging()
    logging.basicConfig(level=logging.INFO)


def before_scenario(context, scenario):
    """Run before each scenario."""
    context.results = {}
    context.checkpoints = {}
    context.temp_dir_obj = None
    context.temp_dir = None
    context.state = None
    context.cleanup_callbacks = []
    context.patches = []


def after_scenario(context, scenario):
    """Run after each scenario."""
    # Run registered cleanup callbacks (LIFO order)
    while context.cleanup_callbacks:
        callback = context.cleanup_callbacks.pop()
        try:
            callback()
        except Exception:  # pragma: no cover - best effort cleanup
            logging.exception("Cleanup callback failed")

    # Stop any active patchers
    for patcher in context.patches:
        try:
            patcher.stop()
        except Exception:  # pragma: no cover
            logging.exception("Failed to stop patcher")
    context.patches.clear()

    # Remove temporary directory if one was created
    if context.temp_dir_obj:
        try:
            context.temp_dir_obj.cleanup()
        except Exception:  # pragma: no cover
            shutil.rmtree(context.temp_dir, ignore_errors=True)
        finally:
            context.temp_dir_obj = None
            context.temp_dir = None


def after_all(context):
    """Run once after all tests."""
    logging.shutdown()


def ensure_temp_dir(context) -> Path:
    """
    Lazily create a per-scenario temporary directory.

    Returns:
        Path object pointing at the workspace directory
    """
    if context.temp_dir is None:
        context.temp_dir_obj = tempfile.TemporaryDirectory(prefix="tactus_behave_")
        context.temp_dir = Path(context.temp_dir_obj.name)
    return context.temp_dir
