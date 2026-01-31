import os
from pathlib import Path


from tactus.cli import app


def test_load_tactus_config_merges_and_sets_env(monkeypatch, tmp_path):
    system_path = tmp_path / "system.yml"
    user_path = tmp_path / "user.yml"
    project_dir = tmp_path / ".tactus"
    project_dir.mkdir()
    project_path = project_dir / "config.yml"

    for path in (system_path, user_path, project_path):
        path.write_text("placeholder")

    class DummyConfigManager:
        def _get_system_config_paths(self):
            return [system_path]

        def _get_user_config_paths(self):
            return [user_path]

        def _load_yaml_file(self, path: Path):
            if path == system_path:
                return {"api_key": "system", "mcp_servers": ["skip"], "list_val": [1]}
            if path == user_path:
                return {"api_key": "user", "nested": {"mode": "fast"}}
            if path == project_path:
                return {"api_key": "project", "flag": True}
            return {}

        def _merge_configs(self, configs):
            merged = {}
            for cfg in configs:
                merged.update(cfg)
            return merged

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("tactus.core.config_manager.ConfigManager", DummyConfigManager)
    monkeypatch.setenv("API_KEY", "preexisting")

    result = app.load_tactus_config()

    assert result["api_key"] == "project"
    assert result["nested"]["mode"] == "fast"
    assert result["flag"] is True
    assert os.environ["API_KEY"] == "preexisting"
    assert os.environ["LIST_VAL"] == "[1]"
    assert os.environ["NESTED_MODE"] == "fast"


def test_load_tactus_config_handles_exceptions(monkeypatch):
    class ExplodingConfigManager:
        def __init__(self):
            raise RuntimeError("boom")

    monkeypatch.setattr("tactus.core.config_manager.ConfigManager", ExplodingConfigManager)

    assert app.load_tactus_config() == {}


def test_load_tactus_config_skips_empty_configs(monkeypatch, tmp_path):
    system_path = tmp_path / "system.yml"
    user_path = tmp_path / "user.yml"
    project_dir = tmp_path / ".tactus"
    project_dir.mkdir()
    project_path = project_dir / "config.yml"

    for path in (system_path, user_path, project_path):
        path.write_text("placeholder")

    class DummyConfigManager:
        def _get_system_config_paths(self):
            return [system_path]

        def _get_user_config_paths(self):
            return [user_path]

        def _load_yaml_file(self, path: Path):
            if path == system_path:
                return {}
            if path == user_path:
                return None
            if path == project_path:
                return {"list_val": [1, 2], "nested": {"keep": 1, "skip": []}}
            return {}

        def _merge_configs(self, configs):
            merged = {}
            for cfg in configs:
                merged.update(cfg)
            return merged

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("tactus.core.config_manager.ConfigManager", DummyConfigManager)
    monkeypatch.setenv("LIST_VAL", "preexisting")

    result = app.load_tactus_config()

    assert result["list_val"] == [1, 2]
    assert os.environ["LIST_VAL"] == "preexisting"
    assert os.environ["NESTED_KEEP"] == "1"


def test_load_tactus_config_without_project_config(monkeypatch, tmp_path):
    system_path = tmp_path / "system.yml"
    user_path = tmp_path / "user.yml"
    system_path.write_text("placeholder")
    user_path.write_text("placeholder")

    class DummyConfigManager:
        def _get_system_config_paths(self):
            return [system_path]

        def _get_user_config_paths(self):
            return [user_path]

        def _load_yaml_file(self, path: Path):
            if path == system_path:
                return {"api_key": "system"}
            if path == user_path:
                return {"api_key": "user"}
            return {}

        def _merge_configs(self, configs):
            merged = {}
            for cfg in configs:
                merged.update(cfg)
            return merged

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("tactus.core.config_manager.ConfigManager", DummyConfigManager)

    result = app.load_tactus_config()

    assert result["api_key"] == "user"


def test_load_tactus_config_project_file_empty(monkeypatch, tmp_path):
    project_dir = tmp_path / ".tactus"
    project_dir.mkdir()
    project_path = project_dir / "config.yml"
    project_path.write_text("placeholder")

    class DummyConfigManager:
        def _get_system_config_paths(self):
            return []

        def _get_user_config_paths(self):
            return []

        def _load_yaml_file(self, path: Path):
            if path == project_path:
                return None
            return {}

        def _merge_configs(self, configs):
            return {"api_key": "fallback"} if configs else {}

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("tactus.core.config_manager.ConfigManager", DummyConfigManager)

    result = app.load_tactus_config()

    assert result == {}


def test_load_tactus_config_skips_non_scalar_nested(monkeypatch, tmp_path):
    system_path = tmp_path / "system.yml"
    system_path.write_text("placeholder")

    class DummyConfigManager:
        def _get_system_config_paths(self):
            return [system_path]

        def _get_user_config_paths(self):
            return []

        def _load_yaml_file(self, path: Path):
            if path == system_path:
                return {"nested": {"list": [1, 2]}}
            return {}

        def _merge_configs(self, configs):
            merged = {}
            for cfg in configs:
                merged.update(cfg)
            return merged

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("tactus.core.config_manager.ConfigManager", DummyConfigManager)

    app.load_tactus_config()

    assert "NESTED_LIST" not in os.environ


def test_load_tactus_config_ignores_unhandled_types(monkeypatch, tmp_path):
    system_path = tmp_path / "system.yml"
    system_path.write_text("placeholder")

    class DummyConfigManager:
        def _get_system_config_paths(self):
            return [system_path]

        def _get_user_config_paths(self):
            return []

        def _load_yaml_file(self, path: Path):
            if path == system_path:
                return {"tuple_value": ("a", "b")}
            return {}

        def _merge_configs(self, configs):
            merged = {}
            for cfg in configs:
                merged.update(cfg)
            return merged

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("tactus.core.config_manager.ConfigManager", DummyConfigManager)

    app.load_tactus_config()

    assert "TUPLE_VALUE" not in os.environ
