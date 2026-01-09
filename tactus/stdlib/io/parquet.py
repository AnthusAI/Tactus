"""
tactus.io.parquet - Apache Parquet file operations for Tactus.

Provides Parquet read/write operations with sandboxing
to the procedure's base directory.

Requires: pyarrow

Usage in .tac files:
    local parquet = require("tactus.io.parquet")

    -- Read Parquet file
    local data = parquet.read("data.parquet")

    -- Write Parquet file
    parquet.write("output.parquet", {
        {name = "Alice", score = 95},
        {name = "Bob", score = 87}
    })
"""

import os
import sys
from typing import Any, Dict, List

try:
    import pyarrow as pa
    import pyarrow.parquet as pq
except ImportError:
    raise ImportError("pyarrow is required for Parquet support. Install with: pip install pyarrow")

# Get context (injected by loader)
_ctx = getattr(sys.modules[__name__], "__tactus_context__", None)


def read(filepath: str) -> List[Dict[str, Any]]:
    """
    Read Parquet file, returning list of dictionaries.

    Args:
        filepath: Path to Parquet file (relative to working directory)

    Returns:
        List of dictionaries, one per row

    Raises:
        FileNotFoundError: If file does not exist
        PermissionError: If path is outside working directory
    """
    if _ctx:
        filepath = _ctx.validate_path(filepath)

    table = pq.read_table(filepath)
    return table.to_pylist()


def write(filepath: str, data: List[Dict[str, Any]]) -> None:
    """
    Write list of dictionaries to Parquet file.

    Args:
        filepath: Path to Parquet file
        data: List of dictionaries to write

    Raises:
        PermissionError: If path is outside working directory
        ValueError: If data is empty or invalid
    """
    if _ctx:
        filepath = _ctx.validate_path(filepath)

    if not data:
        raise ValueError("Cannot write empty data to Parquet")

    # Create parent directories
    os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)

    table = pa.Table.from_pylist(data)
    pq.write_table(table, filepath)


# Explicit exports
__tactus_exports__ = ["read", "write"]
