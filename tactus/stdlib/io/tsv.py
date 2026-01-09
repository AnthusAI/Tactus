"""
tactus.io.tsv - TSV (tab-separated values) file operations for Tactus.

Provides TSV read/write operations with automatic header handling
and sandboxing to the procedure's base directory.

Usage in .tac files:
    local tsv = require("tactus.io.tsv")

    -- Read TSV file
    local data = tsv.read("data.tsv")

    -- Write TSV file
    tsv.write("output.tsv", {
        {name = "Alice", age = 30},
        {name = "Bob", age = 25}
    })
"""

import csv
import os
import sys
from typing import Any, Dict, List, Optional

# Get context (injected by loader)
_ctx = getattr(sys.modules[__name__], "__tactus_context__", None)


def read(filepath: str) -> List[Dict[str, Any]]:
    """
    Read TSV file, returning list of dictionaries with headers as keys.

    Args:
        filepath: Path to TSV file (relative to working directory)

    Returns:
        List of dictionaries, one per row

    Raises:
        FileNotFoundError: If file does not exist
        PermissionError: If path is outside working directory
    """
    if _ctx:
        filepath = _ctx.validate_path(filepath)

    with open(filepath, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        return list(reader)


def write(
    filepath: str, data: List[Dict[str, Any]], options: Optional[Dict[str, Any]] = None
) -> None:
    """
    Write list of dictionaries to TSV file.

    Args:
        filepath: Path to TSV file
        data: List of dictionaries to write
        options: Optional dict with 'headers' key for custom header order

    Raises:
        PermissionError: If path is outside working directory
        ValueError: If data is empty or cannot determine headers
    """
    if _ctx:
        filepath = _ctx.validate_path(filepath)

    if not data:
        raise ValueError("Cannot write empty data to TSV")

    # Determine headers
    options = options or {}
    headers = options.get("headers")
    if not headers:
        headers = list(data[0].keys())

    # Create parent directories
    os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)

    with open(filepath, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers, delimiter="\t")
        writer.writeheader()
        writer.writerows(data)


# Explicit exports
__tactus_exports__ = ["read", "write"]
