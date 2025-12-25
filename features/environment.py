"""
Behave environment configuration for Tactus end‑to‑end tests.

Provides light-weight fixtures commonly used across the feature files
so individual step definitions can focus on behavior instead of setup
and teardown plumbing.
"""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
import yaml
from pathlib import Path


def before_all(context):
    """Run once before all tests."""
    context.config.setup_logging()
    logging.basicConfig(level=logging.INFO)

    # Load .tactus/config.yml and export to environment
    tactus_config_path = Path.cwd() / ".tactus" / "config.yml"
    if tactus_config_path.exists():
        with open(tactus_config_path) as f:
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
