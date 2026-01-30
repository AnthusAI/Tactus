import sys
import types

import pytest
from flask import Flask

from tactus.ide import config_server


class FakeConfigValue:
    def __init__(self, source_type="user", is_env_override=False, original_env_var=None):
        self.source_type = source_type
        self.is_env_override = is_env_override
        self.original_env_var = original_env_var

    def to_dict(self):
        return {
            "source_type": self.source_type,
            "is_env_override": self.is_env_override,
            "original_env_var": self.original_env_var,
        }


class FakeConfigManager:
    def __init__(self):
        self.loaded_configs = [("user:/tmp/config.yml", {"default_provider": "openai"})]

    def load_cascade_with_sources(self, path):
        return {"default_provider": "openai"}, {"default_provider": FakeConfigValue()}


def _make_app():
    app = Flask("config_test")
    app.register_blueprint(config_server.config_bp)
    return app


def test_build_cascade_map():
    loaded = [
        ("user:/path", {"a": {"b": 1}, "list": [{"x": 1}]}),
        ("project:/path", {"a": {"b": 2}}),
    ]
    result = config_server.build_cascade_map(loaded)
    assert result["a"] == "project"
    assert result["a.b"] == "project"
    assert result["list"] == "user"


def test_load_and_save_yaml_file(tmp_path):
    missing = tmp_path / "missing.yml"
    assert config_server.load_yaml_file(missing) is None

    invalid = tmp_path / "invalid.yml"
    invalid.write_text("- item\n- item")
    assert config_server.load_yaml_file(invalid) == {}

    path = tmp_path / "config.yml"
    path.write_text("default_provider: openai\n")
    config_server.save_yaml_file(path, {"default_provider": "bedrock"}, create_backup=True)
    assert path.with_suffix(".yml.bak").exists()


def test_load_yaml_file_handles_exception(monkeypatch, tmp_path):
    path = tmp_path / "config.yml"
    path.write_text("x: 1")

    def boom(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("builtins.open", boom)

    assert config_server.load_yaml_file(path) is None


def test_save_yaml_file_no_backup(tmp_path):
    path = tmp_path / ".tactus" / "config.yml"
    config_server.save_yaml_file(path, {"default_provider": "openai"}, create_backup=False)
    assert path.exists()


def test_get_config_uses_example_template(tmp_path, monkeypatch):
    root = tmp_path
    tactus_dir = root / ".tactus"
    tactus_dir.mkdir()
    example_path = tactus_dir / "config.yml.example"
    example_path.write_text("default_provider: openai\n")

    monkeypatch.setattr(config_server.Path, "cwd", lambda: root)
    monkeypatch.setattr(config_server.Path, "home", lambda: root)
    monkeypatch.setattr(
        "tactus.core.config_manager.ConfigManager", FakeConfigManager, raising=False
    )

    app = _make_app()
    client = app.test_client()
    response = client.get("/api/config")
    payload = response.get_json()
    assert payload["config"]["default_provider"] == "openai"
    assert payload["project_config"]["default_provider"] == "openai"


def test_get_config_skips_example_when_keys_present(tmp_path, monkeypatch):
    tactus_dir = tmp_path / ".tactus"
    tactus_dir.mkdir()
    project_path = tactus_dir / "config.yml"
    project_path.write_text(
        "openai:\n  api_key: sk-test\naws:\n  access_key_id: key\ngoogle:\n  api_key: test\n"
    )

    monkeypatch.setattr(config_server.Path, "cwd", lambda: tmp_path)
    monkeypatch.setattr(config_server.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(
        "tactus.core.config_manager.ConfigManager", FakeConfigManager, raising=False
    )

    called = {"saved": False}

    def fake_save(*_args, **_kwargs):
        called["saved"] = True

    monkeypatch.setattr(config_server, "save_yaml_file", fake_save)

    app = _make_app()
    client = app.test_client()
    response = client.get("/api/config")

    assert response.status_code == 200
    assert called["saved"] is False


def test_get_config_uses_flat_key_compat_and_placeholders(tmp_path, monkeypatch):
    tactus_dir = tmp_path / ".tactus"
    tactus_dir.mkdir()
    example_path = tactus_dir / "config.yml.example"
    example_path.write_text("default_provider: openai\n")
    project_path = tactus_dir / "config.yml"
    project_path.write_text(
        "openai_api_key: your-openai-key\naws_access_key_id: default\n"
        "google:\n  api_key: your-google-key\n"
    )

    monkeypatch.setattr(config_server.Path, "cwd", lambda: tmp_path)
    monkeypatch.setattr(config_server.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(
        "tactus.core.config_manager.ConfigManager", FakeConfigManager, raising=False
    )

    app = _make_app()
    client = app.test_client()
    response = client.get("/api/config")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["project_config"]["default_provider"] == "openai"


def test_get_config_example_save_failure_logs(tmp_path, monkeypatch):
    tactus_dir = tmp_path / ".tactus"
    tactus_dir.mkdir()
    example_path = tactus_dir / "config.yml.example"
    example_path.write_text("default_provider: openai\n")

    monkeypatch.setattr(config_server.Path, "cwd", lambda: tmp_path)
    monkeypatch.setattr(config_server.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(
        "tactus.core.config_manager.ConfigManager", FakeConfigManager, raising=False
    )
    monkeypatch.setattr(config_server, "save_yaml_file", lambda *_args, **_kwargs: 1 / 0)

    app = _make_app()
    client = app.test_client()
    response = client.get("/api/config")

    assert response.status_code == 200


def test_get_config_with_google_key_skips_example(tmp_path, monkeypatch):
    tactus_dir = tmp_path / ".tactus"
    tactus_dir.mkdir()
    example_path = tactus_dir / "config.yml.example"
    example_path.write_text("default_provider: openai\n")
    project_path = tactus_dir / "config.yml"
    project_path.write_text("google:\n  api_key: real-key\n")

    monkeypatch.setattr(config_server.Path, "cwd", lambda: tmp_path)
    monkeypatch.setattr(config_server.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(
        "tactus.core.config_manager.ConfigManager", FakeConfigManager, raising=False
    )

    called = {"saved": False}

    def fake_save(*_args, **_kwargs):
        called["saved"] = True

    monkeypatch.setattr(config_server, "save_yaml_file", fake_save)

    app = _make_app()
    client = app.test_client()
    response = client.get("/api/config")

    assert response.status_code == 200
    assert called["saved"] is False


def test_get_config_google_key_non_dict_keeps_example(tmp_path, monkeypatch):
    tactus_dir = tmp_path / ".tactus"
    tactus_dir.mkdir()
    example_path = tactus_dir / "config.yml.example"
    example_path.write_text("default_provider: openai\n")
    project_path = tactus_dir / "config.yml"
    project_path.write_text("google: invalid\n")

    monkeypatch.setattr(config_server.Path, "cwd", lambda: tmp_path)
    monkeypatch.setattr(config_server.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(
        "tactus.core.config_manager.ConfigManager", FakeConfigManager, raising=False
    )

    app = _make_app()
    client = app.test_client()
    response = client.get("/api/config")

    assert response.status_code == 200


def test_get_config_missing_example_sets_empty_config(tmp_path, monkeypatch):
    monkeypatch.setattr(config_server.Path, "cwd", lambda: tmp_path)
    monkeypatch.setattr(config_server.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(
        "tactus.core.config_manager.ConfigManager", FakeConfigManager, raising=False
    )

    def fake_load(path):
        if str(path).endswith(".tactus/config.yml"):
            return None
        return {}

    monkeypatch.setattr(config_server, "load_yaml_file", fake_load)

    app = _make_app()
    client = app.test_client()
    response = client.get("/api/config")

    assert response.status_code == 200
    assert response.get_json()["project_config"] == {}


def test_get_config_missing_example_with_empty_project(tmp_path, monkeypatch):
    monkeypatch.setattr(config_server.Path, "cwd", lambda: tmp_path)
    monkeypatch.setattr(config_server.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(
        "tactus.core.config_manager.ConfigManager", FakeConfigManager, raising=False
    )

    monkeypatch.setattr(config_server, "load_yaml_file", lambda _path: None)

    app = _make_app()
    client = app.test_client()
    response = client.get("/api/config")

    assert response.status_code == 200
    assert response.get_json()["project_config"] == {}


def test_get_config_empty_project_without_example(tmp_path, monkeypatch):
    monkeypatch.setattr(config_server.Path, "cwd", lambda: tmp_path)
    monkeypatch.setattr(config_server.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(
        "tactus.core.config_manager.ConfigManager", FakeConfigManager, raising=False
    )

    def fake_load(path):
        if str(path).endswith(".tactus/config.yml"):
            return {}
        return {}

    monkeypatch.setattr(config_server, "load_yaml_file", fake_load)

    app = _make_app()
    client = app.test_client()
    response = client.get("/api/config")

    assert response.status_code == 200
    assert response.get_json()["project_config"] == {}


def test_get_config_truthy_project_without_example(tmp_path, monkeypatch):
    monkeypatch.setattr(config_server.Path, "cwd", lambda: tmp_path)
    monkeypatch.setattr(config_server.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(
        "tactus.core.config_manager.ConfigManager", FakeConfigManager, raising=False
    )

    def fake_load(path):
        if str(path).endswith(".tactus/config.yml"):
            return {"ide": {"theme": "dark"}}
        return {}

    monkeypatch.setattr(config_server, "load_yaml_file", fake_load)

    app = _make_app()
    client = app.test_client()
    response = client.get("/api/config")

    assert response.status_code == 200
    assert response.get_json()["project_config"]["ide"]["theme"] == "dark"


def test_get_config_google_key_via_stubbed_load(tmp_path, monkeypatch):
    monkeypatch.setattr(config_server.Path, "cwd", lambda: tmp_path)
    monkeypatch.setattr(config_server.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(
        "tactus.core.config_manager.ConfigManager", FakeConfigManager, raising=False
    )

    def fake_load(path):
        if str(path).endswith(".tactus/config.yml"):
            return {"google": {"api_key": "real-key"}}
        return {}

    monkeypatch.setattr(config_server, "load_yaml_file", fake_load)

    app = _make_app()
    client = app.test_client()
    response = client.get("/api/config")

    assert response.status_code == 200
    assert response.get_json()["project_config"]["google"]["api_key"] == "real-key"


def test_get_config_handles_missing_example(tmp_path, monkeypatch):
    monkeypatch.setattr(config_server.Path, "cwd", lambda: tmp_path)
    monkeypatch.setattr(config_server.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(
        "tactus.core.config_manager.ConfigManager", FakeConfigManager, raising=False
    )

    app = _make_app()
    client = app.test_client()
    response = client.get("/api/config")

    assert response.status_code == 200
    payload = response.get_json()
    assert isinstance(payload["project_config"], dict)


def test_get_config_handles_non_dict_project_config(tmp_path, monkeypatch):
    monkeypatch.setattr(config_server.Path, "cwd", lambda: tmp_path)
    monkeypatch.setattr(config_server.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(
        "tactus.core.config_manager.ConfigManager", FakeConfigManager, raising=False
    )
    monkeypatch.setattr(config_server, "load_yaml_file", lambda _path: ["not", "dict"])

    app = _make_app()
    client = app.test_client()
    response = client.get("/api/config")

    assert response.status_code == 200
    assert response.get_json()["project_config"] == {}


def test_get_config_reports_errors(tmp_path, monkeypatch):
    monkeypatch.setattr(config_server.Path, "cwd", lambda: tmp_path)
    monkeypatch.setattr(config_server.Path, "home", lambda: tmp_path)

    class BoomConfigManager:
        def __init__(self):
            raise RuntimeError("boom")

    monkeypatch.setattr(
        "tactus.core.config_manager.ConfigManager", BoomConfigManager, raising=False
    )

    app = _make_app()
    client = app.test_client()
    response = client.get("/api/config")

    assert response.status_code == 500
    assert "boom" in response.get_json()["error"]


def test_save_config_and_validation(tmp_path, monkeypatch):
    monkeypatch.setattr(config_server.Path, "cwd", lambda: tmp_path)
    monkeypatch.setattr(config_server.Path, "home", lambda: tmp_path)

    app = _make_app()
    client = app.test_client()

    response = client.post("/api/config", json={})
    assert response.status_code == 400

    response = client.post(
        "/api/config", json={"config": {"default_provider": "openai"}, "targetFile": "bad"}
    )
    assert response.status_code == 400

    response = client.post(
        "/api/config", json={"config": {"default_provider": "openai"}, "targetFile": "project"}
    )
    assert response.get_json()["success"] is True
    assert (tmp_path / ".tactus" / "config.yml").exists()

    response = client.post(
        "/api/config", json={"config": {"default_provider": "openai"}, "targetFile": "user"}
    )
    assert response.get_json()["success"] is True
    assert (tmp_path / ".tactus" / "config.yml").exists()


def test_save_config_missing_or_invalid_config(tmp_path, monkeypatch):
    monkeypatch.setattr(config_server.Path, "cwd", lambda: tmp_path)
    monkeypatch.setattr(config_server.Path, "home", lambda: tmp_path)

    app = _make_app()
    client = app.test_client()

    response = client.post("/api/config", json={"config": None})
    assert response.status_code == 400

    response = client.post("/api/config", json={"config": "bad"})
    assert response.status_code == 400


def test_save_config_clears_runtime_caches(tmp_path, monkeypatch):
    monkeypatch.setattr(config_server.Path, "cwd", lambda: tmp_path)
    monkeypatch.setattr(config_server.Path, "home", lambda: tmp_path)

    dummy_server = types.ModuleType("tactus.ide.server")
    called = {"clear": False}

    def fake_clear():
        called["clear"] = True

    dummy_server.clear_runtime_caches = fake_clear
    monkeypatch.setitem(sys.modules, "tactus.ide.server", dummy_server)

    app = _make_app()
    client = app.test_client()
    response = client.post(
        "/api/config", json={"config": {"default_provider": "openai"}, "targetFile": "project"}
    )

    assert response.status_code == 200
    assert called["clear"] is True


def test_save_config_handles_missing_cache_clear(tmp_path, monkeypatch):
    monkeypatch.setattr(config_server.Path, "cwd", lambda: tmp_path)
    monkeypatch.setattr(config_server.Path, "home", lambda: tmp_path)
    monkeypatch.setitem(sys.modules, "tactus.ide.server", types.ModuleType("tactus.ide.server"))

    app = _make_app()
    client = app.test_client()
    response = client.post(
        "/api/config", json={"config": {"default_provider": "openai"}, "targetFile": "project"}
    )

    assert response.status_code == 200


def test_save_config_reports_errors(tmp_path, monkeypatch):
    monkeypatch.setattr(config_server.Path, "cwd", lambda: tmp_path)
    monkeypatch.setattr(config_server.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(config_server, "save_yaml_file", lambda *_args, **_kwargs: 1 / 0)

    app = _make_app()
    client = app.test_client()
    response = client.post(
        "/api/config", json={"config": {"default_provider": "openai"}, "targetFile": "project"}
    )

    assert response.status_code == 500


def test_save_config_by_source(tmp_path, monkeypatch):
    monkeypatch.setattr(config_server.Path, "cwd", lambda: tmp_path)
    monkeypatch.setattr(config_server.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(
        "tactus.core.config_manager.ConfigManager", FakeConfigManager, raising=False
    )

    app = _make_app()
    client = app.test_client()

    response = client.post(
        "/api/config/save-by-source",
        json={"changes": {"default_provider": "openai"}, "target_strategy": "source_aware"},
    )
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["saved_to"]["default_provider"] == "user"
    assert (tmp_path / ".tactus" / "config.yml").exists()


def test_save_config_by_source_validations(tmp_path, monkeypatch):
    monkeypatch.setattr(config_server.Path, "cwd", lambda: tmp_path)
    monkeypatch.setattr(config_server.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(
        "tactus.core.config_manager.ConfigManager", FakeConfigManager, raising=False
    )

    app = _make_app()
    client = app.test_client()

    assert client.post("/api/config/save-by-source", json={}).status_code == 400
    assert client.post("/api/config/save-by-source", json={"changes": None}).status_code == 400
    assert client.post("/api/config/save-by-source", json={"changes": ["bad"]}).status_code == 400


def test_save_config_by_source_env_override(tmp_path, monkeypatch):
    class EnvConfigManager(FakeConfigManager):
        def load_cascade_with_sources(self, path):
            return {"default_provider": "openai"}, {
                "default_provider": FakeConfigValue(
                    source_type="user", is_env_override=True, original_env_var="OPENAI_API_KEY"
                )
            }

    monkeypatch.setattr(config_server.Path, "cwd", lambda: tmp_path)
    monkeypatch.setattr(config_server.Path, "home", lambda: tmp_path)
    monkeypatch.setattr("tactus.core.config_manager.ConfigManager", EnvConfigManager, raising=False)

    app = _make_app()
    client = app.test_client()

    response = client.post(
        "/api/config/save-by-source",
        json={"changes": {"default_provider": "openai"}, "target_strategy": "source_aware"},
    )
    payload = response.get_json()
    assert payload["success"] is False
    assert payload["errors"]


def test_save_config_by_source_system_source_defaults_to_user(tmp_path, monkeypatch):
    class SystemConfigManager(FakeConfigManager):
        def load_cascade_with_sources(self, path):
            return {"default_provider": "openai"}, {
                "default_provider": FakeConfigValue(source_type="system")
            }

    monkeypatch.setattr(config_server.Path, "cwd", lambda: tmp_path)
    monkeypatch.setattr(config_server.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(
        "tactus.core.config_manager.ConfigManager", SystemConfigManager, raising=False
    )

    app = _make_app()
    client = app.test_client()

    response = client.post(
        "/api/config/save-by-source",
        json={"changes": {"default_provider": "openai"}, "target_strategy": "source_aware"},
    )
    payload = response.get_json()
    assert payload["saved_to"]["default_provider"] == "user"


def test_save_config_by_source_reports_errors(tmp_path, monkeypatch):
    monkeypatch.setattr(config_server.Path, "cwd", lambda: tmp_path)
    monkeypatch.setattr(config_server.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(
        "tactus.core.config_manager.ConfigManager", FakeConfigManager, raising=False
    )
    monkeypatch.setattr(config_server, "save_yaml_file", lambda *_args, **_kwargs: 1 / 0)

    app = _make_app()
    client = app.test_client()
    response = client.post(
        "/api/config/save-by-source",
        json={"changes": {"default_provider": "openai"}, "target_strategy": "force_user"},
    )

    assert response.status_code == 500


def test_save_config_by_source_force_user(tmp_path, monkeypatch):
    monkeypatch.setattr(config_server.Path, "cwd", lambda: tmp_path)
    monkeypatch.setattr(config_server.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(
        "tactus.core.config_manager.ConfigManager", FakeConfigManager, raising=False
    )

    app = _make_app()
    client = app.test_client()

    response = client.post(
        "/api/config/save-by-source",
        json={"changes": {"default_provider": "openai"}, "target_strategy": "force_user"},
    )
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["saved_to"]["default_provider"] == "user"


def test_save_config_by_source_uses_project_source(tmp_path, monkeypatch):
    class ProjectConfigManager(FakeConfigManager):
        def load_cascade_with_sources(self, path):
            return {"default_provider": "openai"}, {
                "default_provider": FakeConfigValue(source_type="project")
            }

    monkeypatch.setattr(config_server.Path, "cwd", lambda: tmp_path)
    monkeypatch.setattr(config_server.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(
        "tactus.core.config_manager.ConfigManager", ProjectConfigManager, raising=False
    )

    app = _make_app()
    client = app.test_client()

    response = client.post(
        "/api/config/save-by-source",
        json={"changes": {"default_provider": "openai"}, "target_strategy": "source_aware"},
    )
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["saved_to"]["default_provider"] == "project"


def test_save_config_by_source_defaults_for_new_path(tmp_path, monkeypatch):
    monkeypatch.setattr(config_server.Path, "cwd", lambda: tmp_path)
    monkeypatch.setattr(config_server.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(
        "tactus.core.config_manager.ConfigManager", FakeConfigManager, raising=False
    )

    app = _make_app()
    client = app.test_client()

    response = client.post(
        "/api/config/save-by-source",
        json={"changes": {"new.setting": "ok"}, "target_strategy": "source_aware"},
    )
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["saved_to"]["new.setting"] == "user"


def test_save_config_by_source_force_project(tmp_path, monkeypatch):
    monkeypatch.setattr(config_server.Path, "cwd", lambda: tmp_path)
    monkeypatch.setattr(config_server.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(
        "tactus.core.config_manager.ConfigManager", FakeConfigManager, raising=False
    )

    app = _make_app()
    client = app.test_client()

    response = client.post(
        "/api/config/save-by-source",
        json={"changes": {"default_provider": "openai"}, "target_strategy": "force_project"},
    )
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["saved_to"]["default_provider"] == "project"


def test_set_nested_value_conflict():
    config = {"a": 1}
    with pytest.raises(ValueError, match="not a dict"):
        config_server._set_nested_value(config, "a.b", 2)


def test_set_nested_value_creates_paths():
    config = {}
    config_server._set_nested_value(config, "a.b", 2)
    assert config == {"a": {"b": 2}}


def test_set_nested_value_existing_dict():
    config = {"a": {"b": 1}}
    config_server._set_nested_value(config, "a.c", 2)
    assert config == {"a": {"b": 1, "c": 2}}


def test_validate_config_endpoint():
    app = _make_app()
    client = app.test_client()

    response = client.post("/api/config/validate", json={"config": {"default_provider": "nope"}})
    payload = response.get_json()
    assert payload["valid"] is True
    assert payload["warnings"]

    response = client.post("/api/config/validate", json={"config": "text"})
    payload = response.get_json()
    assert payload["valid"] is False
    assert "Config must be an object" in payload["errors"]

    response = client.post("/api/config/validate", json={"config": {"ide": "nope"}})
    payload = response.get_json()
    assert payload["valid"] is False
    assert "ide config must be an object" in payload["errors"]

    response = client.post("/api/config/validate", json={"config": {"default_provider": "openai"}})
    payload = response.get_json()
    assert payload["valid"] is True


def test_validate_config_ide_non_dict_direct():
    app = _make_app()
    with app.test_request_context(json={"config": {"ide": "nope"}}):
        response = config_server.validate_config()
    payload = response.get_json()
    assert payload["valid"] is False
    assert "ide config must be an object" in payload["errors"]


def test_validate_config_ide_non_dict_list_direct():
    app = _make_app()
    with app.test_request_context(json={"config": {"ide": ["bad"]}}):
        response = config_server.validate_config()
    payload = response.get_json()
    assert payload["valid"] is False
    assert "ide config must be an object" in payload["errors"]


def test_validate_config_missing_body_and_config():
    app = _make_app()
    client = app.test_client()

    response = client.post("/api/config/validate", data="null", content_type="application/json")
    assert response.status_code == 400

    response = client.post("/api/config/validate", json={"config": None})
    assert response.status_code == 400


def test_validate_config_accepts_ide_dict():
    app = _make_app()
    client = app.test_client()

    response = client.post("/api/config/validate", json={"config": {"ide": {"theme": "dark"}}})
    payload = response.get_json()
    assert payload["valid"] is True


def test_register_config_routes_registers_blueprint():
    app = Flask("config_register_test")
    config_server.register_config_routes(app)
    assert "config" in app.blueprints


def test_validate_config_serialization_error(monkeypatch):
    app = _make_app()
    client = app.test_client()

    def boom(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(config_server.yaml, "safe_dump", boom)
    response = client.post("/api/config/validate", json={"config": {"x": "y"}})
    payload = response.get_json()
    assert payload["valid"] is False
    assert "serialized" in payload["errors"][0]


def test_validate_config_reports_errors(monkeypatch):
    class BadRequest:
        @property
        def json(self):
            raise RuntimeError("boom")

    monkeypatch.setattr(config_server, "request", BadRequest())
    app = _make_app()
    with app.app_context():
        response = config_server.validate_config()

    assert response[1] == 500
