"""Tests for stdlib excel, parquet, and hdf5 helpers."""

from pathlib import Path

import pytest
from openpyxl import Workbook

import tactus.stdlib.io.excel as excel_io
import tactus.stdlib.io.parquet as parquet_io
import tactus.stdlib.io.hdf5 as hdf5_io


class FakeContext:
    def __init__(self, base_path: Path):
        self.base_path = base_path

    def validate_path(self, path: str) -> str:
        p = Path(path)
        if p.is_absolute() or ".." in p.parts:
            raise PermissionError(f"Invalid path: {path}")
        return str(self.base_path / path)


@pytest.fixture
def io_context(tmp_path, monkeypatch):
    ctx = FakeContext(tmp_path)
    monkeypatch.setattr(excel_io, "_ctx", ctx, raising=False)
    monkeypatch.setattr(parquet_io, "_ctx", ctx, raising=False)
    monkeypatch.setattr(hdf5_io, "_ctx", ctx, raising=False)
    return tmp_path


def test_excel_write_read_and_sheets(io_context):
    data = [{"name": "Alice", "score": 95}, {"name": "Bob", "score": 87}]
    excel_io.write("scores.xlsx", data, {"sheet": "Scores"})

    rows = excel_io.read("scores.xlsx", {"sheet": "Scores"})
    sheets = excel_io.sheets("scores.xlsx")

    assert rows == data
    assert "Scores" in sheets


def test_excel_write_empty_raises(io_context):
    with pytest.raises(ValueError):
        excel_io.write("empty.xlsx", [])


def test_excel_read_empty_sheet_returns_empty(io_context):
    wb = Workbook()
    wb.save(io_context / "empty_sheet.xlsx")

    rows = excel_io.read("empty_sheet.xlsx")
    assert rows == []


def test_excel_read_default_sheet_and_header_fallback(io_context):
    wb = Workbook()
    ws = wb.active
    ws.append([None])
    ws.append(["value"])
    wb.save(io_context / "headers.xlsx")

    rows = excel_io.read("headers.xlsx")
    assert rows == [{"col_0": "value"}]


def test_parquet_write_and_read(io_context):
    data = [{"name": "Alice", "score": 95}, {"name": "Bob", "score": 87}]
    parquet_io.write("scores.parquet", data)

    rows = parquet_io.read("scores.parquet")

    assert rows == data


def test_parquet_write_empty_raises(io_context):
    with pytest.raises(ValueError):
        parquet_io.write("empty.parquet", [])


def test_parquet_read_missing_file(io_context):
    with pytest.raises(FileNotFoundError):
        parquet_io.read("missing.parquet")


def test_hdf5_write_read_and_list(io_context):
    data = [1, 2, 3]
    hdf5_io.write("data.h5", "group/dataset", data)

    rows = hdf5_io.read("data.h5", "group/dataset")
    datasets = hdf5_io.list("data.h5")

    assert rows == data
    assert "group/dataset" in datasets


def test_hdf5_overwrites_existing_dataset(io_context):
    hdf5_io.write("overwrite.h5", "group/dataset", [1, 2])
    hdf5_io.write("overwrite.h5", "group/dataset", [3])
    assert hdf5_io.read("overwrite.h5", "group/dataset") == [3]


def test_hdf5_read_missing_dataset_raises(io_context):
    hdf5_io.write("missing_dataset.h5", "group/dataset", [1])
    with pytest.raises(KeyError):
        hdf5_io.read("missing_dataset.h5", "group/other")


def test_excel_read_write_without_context(tmp_path, monkeypatch):
    monkeypatch.setattr(excel_io, "_ctx", None, raising=False)
    path = tmp_path / "sheet.xlsx"

    excel_io.write(str(path), [{"name": "Ada"}])
    rows = excel_io.read(str(path))
    assert rows == [{"name": "Ada"}]


def test_parquet_read_write_without_context(tmp_path, monkeypatch):
    monkeypatch.setattr(parquet_io, "_ctx", None, raising=False)
    path = tmp_path / "data.parquet"

    parquet_io.write(str(path), [{"name": "Ada"}])
    rows = parquet_io.read(str(path))
    assert rows == [{"name": "Ada"}]


def test_hdf5_read_write_without_context(tmp_path, monkeypatch):
    monkeypatch.setattr(hdf5_io, "_ctx", None, raising=False)
    path = tmp_path / "data.h5"

    hdf5_io.write(str(path), "group/data", [1, 2])
    rows = hdf5_io.read(str(path), "group/data")
    assert rows == [1, 2]
