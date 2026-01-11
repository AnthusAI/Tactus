"""
tactus.io.fs - Filesystem helpers for Tactus.

Provides safe directory listing and globbing, sandboxed to the procedure's base directory.

Usage in .tac files:
    local fs = require("tactus.io.fs")

    -- List files in a directory
    local entries = fs.list_dir("chapters")

    -- Glob files (sorted by default)
    local qmd_files = fs.glob("chapters/*.qmd")
"""

from __future__ import annotations

import glob as _glob
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Get context (injected by loader)
_ctx = getattr(sys.modules[__name__], "__tactus_context__", None)


def _base_path() -> str:
    if _ctx and getattr(_ctx, "base_path", None):
        return str(_ctx.base_path)
    return os.getcwd()


def _validate_relative_path(path: str) -> None:
    # Keep semantics consistent with other stdlib IO modules:
    # - no absolute paths
    # - no traversal segments
    p = Path(path)
    if p.is_absolute():
        raise PermissionError(f"Absolute paths not allowed: {path}")
    if any(part == ".." for part in p.parts):
        raise PermissionError(f"Path traversal not allowed: {path}")


def list_dir(dirpath: str, options: Optional[Dict[str, Any]] = None) -> List[str]:
    """
    List entries in a directory.

    Args:
        dirpath: Directory path (relative to working directory)
        options:
          - files_only: bool (default True) - include only files
          - dirs_only: bool (default False) - include only directories
          - sort: bool (default True) - sort results

    Returns:
        List of entry paths (relative to working directory)
    """
    options = options or {}
    files_only = bool(options.get("files_only", True))
    dirs_only = bool(options.get("dirs_only", False))
    sort = bool(options.get("sort", True))

    _validate_relative_path(dirpath)

    base = os.path.realpath(_base_path())
    abs_dir = os.path.realpath(os.path.join(base, dirpath))

    # Ensure the directory itself is within base path (symlink-safe via realpath)
    if abs_dir != base and not abs_dir.startswith(base + os.sep):
        raise PermissionError(f"Access denied: path outside working directory: {dirpath}")

    if not os.path.isdir(abs_dir):
        raise FileNotFoundError(f"Directory not found: {dirpath}")

    entries: List[str] = []
    for name in os.listdir(abs_dir):
        abs_child = os.path.realpath(os.path.join(abs_dir, name))
        if abs_child != base and not abs_child.startswith(base + os.sep):
            # Skip symlink escapes
            continue

        is_dir = os.path.isdir(abs_child)
        is_file = os.path.isfile(abs_child)

        if dirs_only and not is_dir:
            continue
        if files_only and not is_file:
            continue

        rel = os.path.relpath(abs_child, base).replace("\\", "/")
        entries.append(rel)

    if sort:
        entries.sort()

    return entries


def glob(pattern: str, options: Optional[Dict[str, Any]] = None) -> List[str]:
    """
    Glob files within the working directory.

    Args:
        pattern: Glob pattern (relative to working directory), e.g. "chapters/*.qmd"
        options:
          - recursive: bool (default False) - enable ** patterns
          - files_only: bool (default True) - include only files
          - dirs_only: bool (default False) - include only directories
          - sort: bool (default True) - sort results

    Returns:
        List of matched paths (relative to working directory)
    """
    options = options or {}
    recursive = bool(options.get("recursive", False))
    files_only = bool(options.get("files_only", True))
    dirs_only = bool(options.get("dirs_only", False))
    sort = bool(options.get("sort", True))

    _validate_relative_path(pattern)

    base = os.path.realpath(_base_path())
    abs_pattern = os.path.realpath(os.path.join(base, pattern))

    # Ensure the pattern root is within base path (symlink-safe via realpath)
    if abs_pattern != base and not abs_pattern.startswith(base + os.sep):
        raise PermissionError(f"Access denied: path outside working directory: {pattern}")

    matches: List[str] = []
    for match in _glob.glob(abs_pattern, recursive=recursive):
        abs_match = os.path.realpath(match)
        if abs_match != base and not abs_match.startswith(base + os.sep):
            # Skip symlink escapes
            continue

        is_dir = os.path.isdir(abs_match)
        is_file = os.path.isfile(abs_match)

        if dirs_only and not is_dir:
            continue
        if files_only and not is_file:
            continue

        rel = os.path.relpath(abs_match, base).replace("\\", "/")
        matches.append(rel)

    if sort:
        matches.sort()

    return matches


__tactus_exports__ = ["list_dir", "glob"]
