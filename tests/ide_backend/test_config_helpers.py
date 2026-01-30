"""Tests for config_server helper functions."""

import sys
from pathlib import Path

import pytest

backend_path = Path(__file__).resolve().parents[2] / "tactus-ide" / "backend"
sys.path.insert(0, str(backend_path))

from config_server import (  # noqa: E402
    build_cascade_map,
    load_yaml_file,
    save_yaml_file,
    _set_nested_value,
)


def test_build_cascade_map_tracks_nested_paths():
    loaded = [
        ("user:/tmp/user.yml", {"a": 1, "nested": {"b": 2}}),
        ("project:/tmp/project.yml", {"nested": {"c": 3}, "items": ["x"]}),
    ]

    cascade = build_cascade_map(loaded)

    assert cascade["a"] == "user"
    assert cascade["nested"] == "project"
    assert cascade["nested.b"] == "user"
    assert cascade["nested.c"] == "project"
    assert cascade["items"] == "project"
    assert "items[0]" not in cascade


def test_load_yaml_file_missing_returns_none(tmp_path):
    path = tmp_path / "missing.yml"
    assert load_yaml_file(path) is None


def test_load_yaml_file_invalid_returns_none(tmp_path):
    path = tmp_path / "invalid.yml"
    path.write_text(":\n", encoding="utf-8")

    assert load_yaml_file(path) is None


def test_save_yaml_file_creates_backup(tmp_path):
    path = tmp_path / "config.yml"
    path.write_text("a: 1\n", encoding="utf-8")

    save_yaml_file(path, {"b": 2}, create_backup=True)

    backup_path = path.with_suffix(".yml.bak")
    assert backup_path.exists()
    assert "a: 1" in backup_path.read_text(encoding="utf-8")


def test_set_nested_value_creates_path():
    config = {}
    _set_nested_value(config, "a.b.c", 3)

    assert config == {"a": {"b": {"c": 3}}}


def test_set_nested_value_conflict_raises():
    config = {"a": "value"}

    with pytest.raises(ValueError):
        _set_nested_value(config, "a.b", 1)
