"""Tests for IDE backend config server API."""

import sys
from pathlib import Path

from flask import Flask
import pytest

backend_path = Path(__file__).resolve().parents[2] / "tactus-ide" / "backend"
sys.path.insert(0, str(backend_path))

import config_server  # noqa: E402


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
    def __init__(self, loaded_configs, source_map, effective_config):
        self.loaded_configs = loaded_configs
        self._source_map = source_map
        self._effective = effective_config

    def load_cascade_with_sources(self, dummy_path):
        return self._effective, self._source_map


@pytest.fixture
def client():
    app = Flask(__name__)
    app.register_blueprint(config_server.config_bp)
    return app.test_client()


@pytest.fixture
def temp_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(config_server.Path, "cwd", lambda: tmp_path)
    monkeypatch.setattr(config_server.Path, "home", lambda: tmp_path)
    return tmp_path


def test_get_config_initializes_from_example(client, temp_paths, monkeypatch):
    (temp_paths / ".tactus").mkdir()
    example_path = temp_paths / ".tactus" / "config.yml.example"
    example_path.write_text("default_provider: openai\n", encoding="utf-8")

    loaded = [("user:/tmp/user.yml", {"ide": {"theme": "dark"}, "list": [1, {"x": 2}]})]
    source_map = {"ide.theme": FakeConfigValue(source_type="user")}
    manager = FakeConfigManager(loaded, source_map, {"default_provider": "openai"})
    monkeypatch.setattr("tactus.core.config_manager.ConfigManager", lambda: manager)

    saved = {}

    def fake_save_yaml(path, config, create_backup=True):
        saved["path"] = path
        saved["config"] = config

    monkeypatch.setattr(config_server, "save_yaml_file", fake_save_yaml)

    response = client.get("/api/config")

    assert response.status_code == 200
    body = response.get_json()
    assert body["config"]["default_provider"] == "openai"
    assert "cascade" in body
    assert saved["path"].name == "config.yml"


def test_get_config_handles_non_dict_project_config(client, temp_paths, monkeypatch):
    manager = FakeConfigManager([], {}, {})
    monkeypatch.setattr("tactus.core.config_manager.ConfigManager", lambda: manager)

    def fake_load_yaml(path):
        if path.name == "config.yml":
            return ["bad"]
        return {}

    monkeypatch.setattr(config_server, "load_yaml_file", fake_load_yaml)

    response = client.get("/api/config")

    assert response.status_code == 200
    assert response.get_json()["project_config"] == {}


def test_get_config_existing_project_config_is_dict(client, temp_paths, monkeypatch):
    (temp_paths / ".tactus").mkdir()
    project_path = temp_paths / ".tactus" / "config.yml"
    project_path.write_text("default_provider: openai\n", encoding="utf-8")

    manager = FakeConfigManager([], {}, {})
    monkeypatch.setattr("tactus.core.config_manager.ConfigManager", lambda: manager)

    response = client.get("/api/config")

    assert response.status_code == 200
    assert response.get_json()["project_config"]["default_provider"] == "openai"


def test_get_config_skips_example_when_keys_present(client, temp_paths, monkeypatch):
    (temp_paths / ".tactus").mkdir()
    project_path = temp_paths / ".tactus" / "config.yml"
    project_path.write_text(
        "openai:\n  api_key: sk-test\naws:\n  profile: default\ngoogle:\n  api_key: test\n",
        encoding="utf-8",
    )

    manager = FakeConfigManager([], {}, {})
    monkeypatch.setattr("tactus.core.config_manager.ConfigManager", lambda: manager)

    saved = {}

    def fake_save_yaml(*_args, **_kwargs):
        saved["called"] = True

    monkeypatch.setattr(config_server, "save_yaml_file", fake_save_yaml)

    response = client.get("/api/config")

    assert response.status_code == 200
    assert saved == {}


def test_get_config_uses_empty_when_no_example(client, temp_paths, monkeypatch):
    manager = FakeConfigManager([], {}, {})
    monkeypatch.setattr("tactus.core.config_manager.ConfigManager", lambda: manager)

    response = client.get("/api/config")

    assert response.status_code == 200
    assert response.get_json()["project_config"] == {}


def test_get_config_example_save_failure_logs_warning(client, temp_paths, monkeypatch, caplog):
    (temp_paths / ".tactus").mkdir()
    example_path = temp_paths / ".tactus" / "config.yml.example"
    example_path.write_text("default_provider: openai\n", encoding="utf-8")

    manager = FakeConfigManager([], {}, {})
    monkeypatch.setattr("tactus.core.config_manager.ConfigManager", lambda: manager)
    monkeypatch.setattr(
        config_server,
        "save_yaml_file",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    with caplog.at_level("WARNING"):
        response = client.get("/api/config")

    assert response.status_code == 200
    assert "Failed to initialize config from example" in caplog.text


def test_get_config_error_returns_500(client, monkeypatch):
    class BoomManager:
        def __init__(self):
            self.loaded_configs = []

        def load_cascade_with_sources(self, dummy_path):
            raise RuntimeError("boom")

    monkeypatch.setattr("tactus.core.config_manager.ConfigManager", BoomManager)

    response = client.get("/api/config")

    assert response.status_code == 500


def test_save_config_validation_errors(client, temp_paths):
    assert client.post("/api/config", json={}).status_code == 400
    assert client.post("/api/config", json={"config": None}).status_code == 400
    assert client.post("/api/config", json={"config": ["x"]}).status_code == 400
    assert (
        client.post("/api/config", json={"config": {"a": 1}, "targetFile": "system"}).status_code
        == 400
    )


def test_save_config_success_project_and_user(client, temp_paths, monkeypatch):
    saved = []

    def fake_save_yaml(path, config, create_backup=True):
        saved.append((path, config, create_backup))

    monkeypatch.setattr(config_server, "save_yaml_file", fake_save_yaml)

    response = client.post("/api/config", json={"config": {"a": 1}, "targetFile": "project"})
    assert response.status_code == 200

    response = client.post("/api/config", json={"config": {"b": 2}, "targetFile": "user"})
    assert response.status_code == 200
    assert len(saved) == 2


def test_save_config_error_returns_500(client, temp_paths, monkeypatch):
    monkeypatch.setattr(
        config_server,
        "save_yaml_file",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    response = client.post("/api/config", json={"config": {"a": 1}})

    assert response.status_code == 500


def test_save_config_by_source_validations(client, temp_paths):
    assert client.post("/api/config/save-by-source", json={}).status_code == 400
    assert client.post("/api/config/save-by-source", json={"changes": None}).status_code == 400
    assert client.post("/api/config/save-by-source", json={"changes": ["x"]}).status_code == 400


def test_save_config_by_source_strategies(client, temp_paths, monkeypatch):
    source_map = {
        "env.value": FakeConfigValue(
            source_type="user", is_env_override=True, original_env_var="ENV_VAR"
        ),
        "user.value": FakeConfigValue(source_type="user"),
        "project.value": FakeConfigValue(source_type="project"),
        "system.value": FakeConfigValue(source_type="system"),
    }
    manager = FakeConfigManager([], source_map, {})
    monkeypatch.setattr("tactus.core.config_manager.ConfigManager", lambda: manager)

    saved = []
    monkeypatch.setattr(
        config_server, "save_yaml_file", lambda path, config, create_backup=True: saved.append(path)
    )

    response = client.post(
        "/api/config/save-by-source",
        json={
            "changes": {
                "env.value": "x",
                "user.value": "y",
                "project.value": "z",
                "system.value": "w",
                "new.value": 1,
            },
            "target_strategy": "source_aware",
        },
    )
    body = response.get_json()
    assert body["success"] is False
    assert "env.value" in body["errors"][0]
    assert body["saved_to"]["user.value"] == "user"
    assert body["saved_to"]["project.value"] == "project"

    response = client.post(
        "/api/config/save-by-source",
        json={"changes": {"a.b": 1}, "target_strategy": "force_user"},
    )
    assert response.get_json()["saved_to"]["a.b"] == "user"

    response = client.post(
        "/api/config/save-by-source",
        json={"changes": {"c.d": 2}, "target_strategy": "force_project"},
    )
    assert response.get_json()["saved_to"]["c.d"] == "project"

    assert any(path.name == "config.yml" for path in saved)


def test_save_config_by_source_error_returns_500(client, temp_paths, monkeypatch):
    class BoomManager:
        def __init__(self):
            self.loaded_configs = []

        def load_cascade_with_sources(self, dummy_path):
            raise RuntimeError("boom")

    monkeypatch.setattr("tactus.core.config_manager.ConfigManager", BoomManager)

    response = client.post("/api/config/save-by-source", json={"changes": {"a": 1}})

    assert response.status_code == 500


def test_set_nested_value_conflict_raises():
    config = {"a": 1}

    with pytest.raises(ValueError):
        config_server._set_nested_value(config, "a.b", 2)


def test_set_nested_value_creates_path():
    config = {}

    config_server._set_nested_value(config, "a.b", 3)

    assert config["a"]["b"] == 3


def test_set_nested_value_existing_dict_path():
    config = {"a": {}}

    config_server._set_nested_value(config, "a.b", 4)

    assert config["a"]["b"] == 4


def test_validate_config_paths(client):
    assert client.post("/api/config/validate", json={}).status_code == 400
    assert client.post("/api/config/validate", json={"config": None}).status_code == 400

    response = client.post("/api/config/validate", json={"config": ["x"]})
    assert response.get_json()["valid"] is False

    response = client.post(
        "/api/config/validate",
        json={"config": {"default_provider": "unknown", "ide": "bad"}},
    )
    body = response.get_json()
    assert body["valid"] is False
    assert body["warnings"]
    assert body["errors"]

    response = client.post(
        "/api/config/validate",
        json={"config": {"default_provider": "openai", "ide": {}}},
    )
    body = response.get_json()
    assert body["valid"] is True
    assert body["warnings"] == []
    assert body["errors"] == []


def test_validate_config_yaml_error(client, monkeypatch):
    monkeypatch.setattr(
        config_server.yaml,
        "safe_dump",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    response = client.post("/api/config/validate", json={"config": {"a": 1}})

    assert response.get_json()["valid"] is False


def test_validate_config_missing_body_and_config(client):
    response = client.post("/api/config/validate", data="null", content_type="application/json")
    assert response.status_code == 400

    response = client.post("/api/config/validate", json={"config": None})
    assert response.status_code == 400


def test_validate_config_warnings_and_errors(client):
    response = client.post(
        "/api/config/validate",
        json={"config": {"default_provider": "unknown", "ide": "bad"}},
    )
    body = response.get_json()
    assert body["warnings"]
    assert body["errors"]


def test_validate_config_exception_returns_500(monkeypatch):
    class BrokenRequest:
        @property
        def json(self):
            raise RuntimeError("boom")

    app = Flask(__name__)
    with app.app_context():
        monkeypatch.setattr(config_server, "request", BrokenRequest())
        response, status = config_server.validate_config()

    assert status == 500


def test_register_config_routes_registers_blueprint():
    app = Flask(__name__)

    config_server.register_config_routes(app)

    assert "config" in app.blueprints


def test_load_yaml_file_failure_returns_none(tmp_path, monkeypatch):
    config_path = tmp_path / "config.yml"
    config_path.write_text("bad: [", encoding="utf-8")

    monkeypatch.setattr(
        config_server.yaml,
        "safe_load",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    assert config_server.load_yaml_file(config_path) is None


def test_save_yaml_file_creates_backup(tmp_path):
    path = tmp_path / "config.yml"
    path.write_text("a: 1\n", encoding="utf-8")

    config_server.save_yaml_file(path, {"a": 2}, create_backup=True)

    assert path.with_suffix(".yml.bak").exists()


def test_save_yaml_file_skips_backup(tmp_path):
    path = tmp_path / "config.yml"
    path.write_text("a: 1\n", encoding="utf-8")

    config_server.save_yaml_file(path, {"a": 2}, create_backup=False)

    assert not path.with_suffix(".yml.bak").exists()
