"""
Tactus CLI module.
"""

from __future__ import annotations

from typing import Any


def main(*args: Any, **kwargs: Any):
    # Avoid importing tactus.cli.app at package import time.
    # This prevents runpy warnings when running: python -m tactus.cli.app
    from tactus.cli.app import main as _main

    return _main(*args, **kwargs)


__all__ = ["main"]
