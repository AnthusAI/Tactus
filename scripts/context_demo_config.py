"""
Helpers for loading Tactus config in demo scripts.
"""

from __future__ import annotations

from pathlib import Path
import os

from tactus.core.config_manager import ConfigManager


def ensure_openai_api_key_from_config() -> bool:
    """
    Ensure OPENAI_API_KEY is set, pulling from .tactus/config.yml if needed.

    :return: True if OPENAI_API_KEY is set or was loaded, False otherwise.
    :rtype: bool
    """
    if os.environ.get("OPENAI_API_KEY"):
        return True

    config = ConfigManager().load_cascade(Path.cwd() / "demo.tac")
    key = config.get("openai_api_key")
    if not key and isinstance(config.get("openai"), dict):
        key = config["openai"].get("api_key")

    if key:
        os.environ["OPENAI_API_KEY"] = key
        return True

    return False
