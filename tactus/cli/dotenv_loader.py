"""Load `.env` files into the process environment for the CLI."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def _load_dotenv_file(path: Path) -> None:
    """If ``path`` is a file, load key=value pairs (does not override existing env)."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        logger.debug("python-dotenv is not installed; skipping %s", path)
        return
    if path.is_file():
        load_dotenv(path, override=False)


def load_dotenv_in_directory(directory: Path) -> None:
    """Load ``.env`` then ``.env.local`` from ``directory`` if present."""
    _load_dotenv_file(directory / ".env")
    _load_dotenv_file(directory / ".env.local")


def load_dotenv_for_cwd() -> None:
    """Load env files from the current working directory."""
    load_dotenv_in_directory(Path.cwd())


def load_dotenv_next_to_procedure(procedure_path: Path) -> None:
    """Load env files from the directory containing the procedure file (or directory)."""
    resolved = procedure_path.resolve()
    if resolved.is_file():
        load_dotenv_in_directory(resolved.parent)
    elif resolved.is_dir():
        load_dotenv_in_directory(resolved)
