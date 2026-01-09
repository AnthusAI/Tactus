"""
tactus.io.hdf5 - HDF5 file operations for Tactus.

Provides HDF5 dataset read/write operations with sandboxing
to the procedure's base directory.

Requires: h5py

Usage in .tac files:
    local hdf5 = require("tactus.io.hdf5")

    -- Read dataset from HDF5 file
    local data = hdf5.read("data.h5", "measurements/temperature")

    -- Write dataset to HDF5 file
    hdf5.write("output.h5", "results/scores", {95, 87, 92, 88})

    -- List all datasets in file
    local datasets = hdf5.list("data.h5")
"""

import os
import sys
from typing import Any, List

try:
    import h5py
    import numpy as np
except ImportError:
    raise ImportError("h5py is required for HDF5 support. Install with: pip install h5py")

# Get context (injected by loader)
_ctx = getattr(sys.modules[__name__], "__tactus_context__", None)


def read(filepath: str, dataset: str) -> List[Any]:
    """
    Read dataset from HDF5 file.

    Args:
        filepath: Path to HDF5 file (relative to working directory)
        dataset: Dataset path within the HDF5 file (e.g., "group/dataset")

    Returns:
        Dataset contents as a list

    Raises:
        FileNotFoundError: If file does not exist
        KeyError: If dataset does not exist in file
        PermissionError: If path is outside working directory
    """
    if _ctx:
        filepath = _ctx.validate_path(filepath)

    with h5py.File(filepath, "r") as f:
        return f[dataset][:].tolist()


def write(filepath: str, dataset: str, data: List[Any]) -> None:
    """
    Write data to HDF5 dataset.

    If the dataset already exists, it will be replaced.
    Parent groups will be created automatically.

    Args:
        filepath: Path to HDF5 file
        dataset: Dataset path within the HDF5 file (e.g., "group/dataset")
        data: Data to write (list or nested lists for multi-dimensional arrays)

    Raises:
        PermissionError: If path is outside working directory
        ValueError: If data is invalid
    """
    if _ctx:
        filepath = _ctx.validate_path(filepath)

    # Create parent directories
    os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)

    with h5py.File(filepath, "a") as f:
        # Delete existing dataset if present
        if dataset in f:
            del f[dataset]

        # Create dataset
        f.create_dataset(dataset, data=np.array(data))


def list(filepath: str) -> List[str]:
    """
    List all datasets in HDF5 file.

    Args:
        filepath: Path to HDF5 file

    Returns:
        List of dataset paths

    Raises:
        FileNotFoundError: If file does not exist
        PermissionError: If path is outside working directory
    """
    if _ctx:
        filepath = _ctx.validate_path(filepath)

    datasets = []

    with h5py.File(filepath, "r") as f:

        def visitor(name, obj):
            if isinstance(obj, h5py.Dataset):
                datasets.append(name)

        f.visititems(visitor)

    return datasets


# Explicit exports
__tactus_exports__ = ["read", "write", "list"]
