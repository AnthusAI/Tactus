"""Tests for import-time dependency errors in stdlib IO modules."""

import builtins
import importlib.util

import pytest

import tactus.stdlib.io.excel as excel_io
import tactus.stdlib.io.parquet as parquet_io
import tactus.stdlib.io.hdf5 as hdf5_io


def _load_module_with_missing_dep(module_path: str, dep_name: str):
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == dep_name:
            raise ImportError("missing")
        return real_import(name, *args, **kwargs)

    spec = importlib.util.spec_from_file_location(f"_missing_{dep_name}", module_path)
    module = importlib.util.module_from_spec(spec)
    try:
        builtins.__import__ = fake_import
        spec.loader.exec_module(module)
    finally:
        builtins.__import__ = real_import


def test_excel_import_error_when_openpyxl_missing():
    with pytest.raises(ImportError, match="openpyxl"):
        _load_module_with_missing_dep(excel_io.__file__, "openpyxl")


def test_parquet_import_error_when_pyarrow_missing():
    with pytest.raises(ImportError, match="pyarrow"):
        _load_module_with_missing_dep(parquet_io.__file__, "pyarrow")


def test_hdf5_import_error_when_h5py_missing():
    with pytest.raises(ImportError, match="h5py"):
        _load_module_with_missing_dep(hdf5_io.__file__, "h5py")
