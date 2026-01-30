"""
Tests for the configuration manager and cascade system.
"""

import pytest
import yaml
from tactus.core.config_manager import ConfigManager, ConfigValue


@pytest.fixture
def config_manager():
    """Create a config manager instance."""
    return ConfigManager()


@pytest.fixture
def temp_procedure(tmp_path):
    """Create a temporary procedure file."""
    procedure_file = tmp_path / "test.tac"
    procedure_file.write_text("-- Test procedure\nagent('test', {})")
    return procedure_file


def test_config_manager_initialization(config_manager):
    """Test that config manager initializes correctly."""
    assert config_manager is not None
    assert config_manager.loaded_configs == []


def test_find_sidecar_config_tac_yml(tmp_path, config_manager):
    """Test finding sidecar config with .tac.yml extension."""
    procedure = tmp_path / "procedure.tac"
    procedure.touch()

    sidecar = tmp_path / "procedure.tac.yml"
    sidecar.write_text("tool_paths: ['./tools']")

    found = config_manager._find_sidecar_config(procedure)
    assert found == sidecar


def test_find_sidecar_config_yml(tmp_path, config_manager):
    """Test finding sidecar config with .yml extension."""
    procedure = tmp_path / "procedure.tac"
    procedure.touch()

    sidecar = tmp_path / "procedure.yml"
    sidecar.write_text("tool_paths: ['./tools']")

    found = config_manager._find_sidecar_config(procedure)
    assert found == sidecar


def test_sidecar_priority_tac_yml_over_yml(tmp_path, config_manager):
    """Test that .tac.yml takes priority over .yml."""
    procedure = tmp_path / "procedure.tac"
    procedure.touch()

    # Create both sidecar variants
    sidecar_tac_yml = tmp_path / "procedure.tac.yml"
    sidecar_tac_yml.write_text("priority: high")

    sidecar_yml = tmp_path / "procedure.yml"
    sidecar_yml.write_text("priority: low")

    found = config_manager._find_sidecar_config(procedure)
    assert found == sidecar_tac_yml


def test_no_sidecar_config(tmp_path, config_manager):
    """Test when no sidecar config exists."""
    procedure = tmp_path / "procedure.tac"
    procedure.touch()

    found = config_manager._find_sidecar_config(procedure)
    assert found is None


def test_sidecar_config_ignored_for_non_tac(tmp_path, config_manager):
    procedure = tmp_path / "procedure.txt"
    procedure.touch()

    found = config_manager._find_sidecar_config(procedure)
    assert found is None


def test_load_yaml_file(tmp_path, config_manager):
    """Test loading a YAML configuration file."""
    config_file = tmp_path / "config.yml"
    config_data = {"tool_paths": ["./tools"], "default_model": "gpt-4o"}
    config_file.write_text(yaml.dump(config_data))

    loaded = config_manager._load_yaml_file(config_file)
    assert loaded == config_data


def test_load_invalid_yaml(tmp_path, config_manager):
    """Test handling of invalid YAML files."""
    config_file = tmp_path / "bad.yml"
    config_file.write_text("invalid: yaml: content:")

    loaded = config_manager._load_yaml_file(config_file)
    assert loaded is None


def test_deep_merge_simple_values(config_manager):
    """Test merging simple values."""
    base = {"key1": "value1", "key2": "value2"}
    override = {"key2": "new_value2", "key3": "value3"}

    result = config_manager._deep_merge(base, override)

    assert result == {"key1": "value1", "key2": "new_value2", "key3": "value3"}


def test_deep_merge_lists_extend(config_manager):
    """Test that lists are extended (combined) by default."""
    base = {"tool_paths": ["./common"]}
    override = {"tool_paths": ["./specific"]}

    result = config_manager._deep_merge(base, override)

    assert result["tool_paths"] == ["./common", "./specific"]


def test_deep_merge_lists_no_duplicates(config_manager):
    """Test that list merging removes duplicates."""
    base = {"tool_paths": ["./tools", "./common"]}
    override = {"tool_paths": ["./common", "./specific"]}

    result = config_manager._deep_merge(base, override)

    # Should have all unique items
    assert set(result["tool_paths"]) == {"./tools", "./common", "./specific"}
    # Should preserve order from base, then add new from override
    assert result["tool_paths"] == ["./tools", "./common", "./specific"]


def test_deep_merge_nested_dicts(config_manager):
    """Test deep merging of nested dictionaries."""
    base = {"aws": {"region": "us-east-1", "timeout": 30}}
    override = {"aws": {"region": "us-west-2", "retries": 3}}

    result = config_manager._deep_merge(base, override)

    assert result == {"aws": {"region": "us-west-2", "timeout": 30, "retries": 3}}


def test_merge_configs_multiple(config_manager):
    """Test merging multiple configurations."""
    configs = [
        {"tool_paths": ["./common"], "model": "gpt-4o"},
        {"tool_paths": ["./specific"], "temperature": 0.7},
        {"model": "gpt-4o-mini"},
    ]

    result = config_manager._merge_configs(configs)

    assert result["tool_paths"] == ["./common", "./specific"]
    assert result["model"] == "gpt-4o-mini"  # Last one wins
    assert result["temperature"] == 0.7


def test_merge_configs_empty(config_manager):
    assert config_manager._merge_configs([]) == {}


def test_load_cascade_with_sidecar(tmp_path, config_manager):
    """Test loading configuration cascade with sidecar file."""
    # Create procedure
    procedure = tmp_path / "procedure.tac"
    procedure.write_text("-- Test")

    # Create sidecar config
    sidecar = tmp_path / "procedure.tac.yml"
    sidecar.write_text(yaml.dump({"tool_paths": ["./tools"]}))

    result = config_manager.load_cascade(procedure)

    assert "tool_paths" in result
    assert "./tools" in result["tool_paths"]


def test_load_cascade_without_sidecar(tmp_path, config_manager):
    """Test loading configuration cascade without sidecar file."""
    # Create procedure
    procedure = tmp_path / "procedure.tac"
    procedure.write_text("-- Test")

    result = config_manager.load_cascade(procedure)

    # Should still return a dict (possibly empty or from environment)
    assert isinstance(result, dict)


def test_find_directory_configs(tmp_path, config_manager):
    """Test finding .tactus/config.yml files in directory tree."""
    # Create nested directory structure
    level1 = tmp_path / "level1"
    level2 = level1 / "level2"
    level3 = level2 / "level3"
    level3.mkdir(parents=True)

    # Create config files at different levels
    (level1 / ".tactus").mkdir()
    config1 = level1 / ".tactus" / "config.yml"
    config1.write_text("level: 1")

    (level2 / ".tactus").mkdir()
    config2 = level2 / ".tactus" / "config.yml"
    config2.write_text("level: 2")

    # Find configs from level3
    configs = config_manager._find_directory_configs(level3)

    # Should find both configs in order (root to leaf)
    assert len(configs) == 2
    assert configs[0] == config1
    assert configs[1] == config2


def test_environment_variable_loading(config_manager, monkeypatch):
    """Test loading configuration from environment variables."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-west-2")

    env_config = config_manager._load_from_environment()

    # Keys are now nested to match config file structure
    assert env_config["openai"]["api_key"] == "test-key"
    assert env_config["aws"]["default_region"] == "us-west-2"


def test_cascade_priority_order(tmp_path, config_manager, monkeypatch):
    """Test that configuration cascade respects priority order."""
    # Set environment variable (lowest priority)
    monkeypatch.setenv("OPENAI_API_KEY", "env-key")

    # Create root config
    root_config = tmp_path / ".tactus"
    root_config.mkdir()
    (root_config / "config.yml").write_text(
        yaml.dump({"openai_api_key": "root-key", "tool_paths": ["./root_tools"]})
    )

    # Create procedure in subdirectory
    subdir = tmp_path / "procedures"
    subdir.mkdir()
    procedure = subdir / "test.tac"
    procedure.write_text("-- Test")

    # Create sidecar config (highest priority)
    sidecar = subdir / "test.tac.yml"
    sidecar.write_text(yaml.dump({"tool_paths": ["./sidecar_tools"]}))

    # Change to tmp_path as cwd
    monkeypatch.chdir(tmp_path)

    result = config_manager.load_cascade(procedure)

    # Sidecar tool_paths should be included
    assert "./sidecar_tools" in result["tool_paths"]
    # Root tool_paths should also be included (lists extend)
    assert "./root_tools" in result["tool_paths"]


def test_load_cascade_includes_system_and_user_configs(tmp_path, config_manager, monkeypatch):
    system_config = tmp_path / "system.yml"
    user_config = tmp_path / "user.yml"
    system_config.write_text(yaml.dump({"system": {"flag": True}}))
    user_config.write_text(yaml.dump({"user": {"name": "alice"}}))

    monkeypatch.setattr(config_manager, "_get_system_config_paths", lambda: [system_config])
    monkeypatch.setattr(config_manager, "_get_user_config_paths", lambda: [user_config])
    monkeypatch.setattr(config_manager, "_find_directory_configs", lambda _path: [])

    procedure = tmp_path / "proc.tac"
    procedure.write_text("-- test")
    monkeypatch.chdir(tmp_path)

    merged = config_manager.load_cascade(procedure)

    assert merged["system"]["flag"] is True
    assert merged["user"]["name"] == "alice"


def test_load_cascade_includes_parent_config(tmp_path, config_manager, monkeypatch):
    parent_config = tmp_path / "parent" / ".tactus" / "config.yml"
    parent_config.parent.mkdir(parents=True)
    parent_config.write_text(yaml.dump({"parent": {"flag": True}}))

    procedure_dir = tmp_path / "parent" / "proc"
    procedure_dir.mkdir(parents=True)
    procedure = procedure_dir / "test.tac"
    procedure.write_text("-- test")

    monkeypatch.setattr(config_manager, "_find_directory_configs", lambda _path: [parent_config])
    monkeypatch.setattr(config_manager, "_get_system_config_paths", lambda: [])
    monkeypatch.setattr(config_manager, "_get_user_config_paths", lambda: [])
    monkeypatch.setattr(config_manager, "_load_from_environment", lambda: {})
    monkeypatch.chdir(tmp_path)

    merged = config_manager.load_cascade(procedure)

    assert merged["parent"]["flag"] is True


def test_load_cascade_skips_empty_configs(tmp_path, config_manager, monkeypatch):
    system_config = tmp_path / "system.yml"
    user_config = tmp_path / "user.yml"
    root_config = tmp_path / ".tactus" / "config.yml"
    parent_config = tmp_path / "parent" / ".tactus" / "config.yml"
    local_config = tmp_path / "proc" / ".tactus" / "config.yml"
    sidecar_config = tmp_path / "proc" / "test.tac.yml"

    parent_config.parent.mkdir(parents=True)
    local_config.parent.mkdir(parents=True)
    root_config.parent.mkdir(parents=True)

    for path in [
        system_config,
        user_config,
        root_config,
        parent_config,
        local_config,
        sidecar_config,
    ]:
        path.write_text("noop: true")

    procedure = tmp_path / "proc" / "test.tac"
    procedure.write_text("-- test")

    monkeypatch.setattr(config_manager, "_get_system_config_paths", lambda: [system_config])
    monkeypatch.setattr(config_manager, "_get_user_config_paths", lambda: [user_config])
    monkeypatch.setattr(config_manager, "_find_directory_configs", lambda _path: [parent_config])
    monkeypatch.setattr(config_manager, "_load_yaml_file", lambda _path: {})
    monkeypatch.setattr(config_manager, "_load_from_environment", lambda: {})
    monkeypatch.chdir(tmp_path)

    result = config_manager.load_cascade(procedure)

    assert result == {}
    assert config_manager.loaded_configs == []


def test_environment_boolean_and_tool_paths(config_manager, monkeypatch):
    monkeypatch.setenv("TACTUS_CONTROL_ENABLED", "true")
    monkeypatch.setenv("TOOL_PATHS", '["./tools"]')

    env_config = config_manager._load_from_environment()

    assert env_config["control"]["enabled"] is True
    assert env_config["tool_paths"] == ["./tools"]


def test_environment_invalid_tool_paths_logs_warning(config_manager, monkeypatch):
    monkeypatch.setenv("TOOL_PATHS", "not-json")

    env_config = config_manager._load_from_environment()

    assert "tool_paths" not in env_config


def test_environment_string_value_mapping(config_manager, monkeypatch):
    monkeypatch.setenv("TACTUS_DEFAULT_PROVIDER", "openai")

    env_config = config_manager._load_from_environment()

    assert env_config["default_provider"] == "openai"
    assert config_manager.env_var_mapping["default_provider"] == "TACTUS_DEFAULT_PROVIDER"


def test_get_system_config_paths_windows_branch(config_manager, monkeypatch):
    import pathlib
    import tactus.core.config_manager as config_manager_module

    monkeypatch.setattr("os.name", "nt", raising=False)
    monkeypatch.setenv("PROGRAMDATA", r"C:\ProgramData")
    monkeypatch.setattr(config_manager_module, "Path", pathlib.PureWindowsPath)

    paths = config_manager._get_system_config_paths()
    assert str(paths[0]).endswith("ProgramData\\tactus\\config.yml")


def test_get_user_config_paths_xdg(config_manager, monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    paths = config_manager._get_user_config_paths()

    assert paths[0] == tmp_path / "tactus" / "config.yml"


def test_get_user_config_paths_dedup(config_manager, monkeypatch):
    import tactus.core.config_manager as config_manager_module

    class FakePath:
        def __init__(self, path: str):
            self.path = path

        def __truediv__(self, part: str) -> "FakePath":
            if self.path.endswith("/"):
                return FakePath(f"{self.path}{part}")
            return FakePath(f"{self.path}/{part}")

        def __eq__(self, other: object) -> bool:
            if not isinstance(other, FakePath):
                return False
            return self._canonical() == other._canonical()

        def __hash__(self) -> int:
            return hash(self._canonical())

        def _canonical(self) -> str:
            return self.path.replace("/.tactus/tactus/", "/.tactus/")

        def __repr__(self) -> str:
            return f"FakePath({self.path!r})"

        @classmethod
        def home(cls) -> "FakePath":
            return cls("/home")

    monkeypatch.setenv("XDG_CONFIG_HOME", "/home/.tactus")
    monkeypatch.setattr(config_manager_module, "Path", FakePath)

    paths = config_manager._get_user_config_paths()

    assert len(paths) == 1


def test_deep_merge_with_tracking_list_override(config_manager):
    config_manager.env_var_mapping = {"tool_paths": "TACTUS_TOOL_PATHS"}
    base = {"tool_paths": ["./base"]}
    override = {"tool_paths": ["./override"]}

    merged, source_map = config_manager._deep_merge_with_tracking(
        base, override, "base", "environment", "", {}
    )

    assert merged["tool_paths"] == ["./base", "./override"]
    assert source_map["tool_paths"].original_env_var == "TACTUS_TOOL_PATHS"


def test_deep_merge_with_tracking_list_duplicate(config_manager):
    base = {"tool_paths": ["./shared", "./base"]}
    override = {"tool_paths": ["./shared", "./override"]}

    merged, source_map = config_manager._deep_merge_with_tracking(
        base, override, "base", "user", "", {}
    )

    assert merged["tool_paths"] == ["./shared", "./base", "./override"]
    assert source_map["tool_paths"].override_chain[-1][1] == ["./shared", "./override"]


def test_track_nested_values_without_overwrite(config_manager):
    source_map = {
        "root.value": ConfigValue(value=1, source="base", source_type="base", path="root.value")
    }

    config_manager._track_nested_values(
        {"value": 2, "nested": {"child": 3}},
        source="override",
        source_type="override",
        path_prefix="root",
        source_map=source_map,
        overwrite=False,
    )

    assert source_map["root.value"].value == 1
    assert source_map["root.nested.child"].value == 3


def test_track_nested_values_without_overwrite_lists(config_manager):
    source_map = {
        "items[0]": ConfigValue(value=1, source="base", source_type="base", path="items[0]")
    }

    config_manager._track_nested_values(
        [{"child": 2}, {"child": 3}],
        source="override",
        source_type="override",
        path_prefix="items",
        source_map=source_map,
        overwrite=False,
    )

    assert source_map["items[0]"].value == 1
    assert source_map["items[1].child"].value == 3


def test_track_nested_values_without_overwrite_scalar_list(config_manager):
    source_map = {
        "items[0]": ConfigValue(value=1, source="base", source_type="base", path="items[0]")
    }

    config_manager._track_nested_values(
        [1],
        source="override",
        source_type="override",
        path_prefix="items",
        source_map=source_map,
        overwrite=False,
    )

    assert source_map["items[0]"].value == 1


def test_track_nested_values_scalar_is_ignored(config_manager):
    source_map = {}

    config_manager._track_nested_values(
        "value", source="base", source_type="base", path_prefix="root", source_map=source_map
    )

    assert source_map == {}


def test_track_nested_values_dict_skip_recurses(config_manager):
    source_map = {
        "root.nested": ConfigValue(value={}, source="base", source_type="base", path="root.nested")
    }

    config_manager._track_nested_values(
        {"nested": {"child": 1}},
        source="override",
        source_type="override",
        path_prefix="root",
        source_map=source_map,
        overwrite=False,
    )

    assert source_map["root.nested.child"].value == 1


def test_track_nested_values_list_nested(config_manager):
    source_map = {
        "items[0]": ConfigValue(value={}, source="base", source_type="base", path="items[0]")
    }

    config_manager._track_nested_values(
        [{"child": 1}],
        source="override",
        source_type="override",
        path_prefix="items",
        source_map=source_map,
        overwrite=False,
    )

    assert source_map["items[0].child"].value == 1


def test_track_nested_values_list_of_dicts(config_manager):
    source_map = {}

    config_manager._track_nested_values(
        [{"child": 2}, {"child": 3}],
        source="base",
        source_type="project",
        path_prefix="items",
        source_map=source_map,
    )

    assert source_map["items[0].child"].value == 2
    assert source_map["items[1].child"].value == 3


def test_load_cascade_with_sources_no_configs(tmp_path, config_manager, monkeypatch):
    procedure = tmp_path / "proc.tac"
    procedure.write_text("-- test")
    monkeypatch.setattr(config_manager, "_load_from_environment", lambda: {})
    monkeypatch.setattr(config_manager, "_get_system_config_paths", lambda: [])
    monkeypatch.setattr(config_manager, "_get_user_config_paths", lambda: [])
    monkeypatch.setattr(config_manager, "_find_directory_configs", lambda _path: [])
    monkeypatch.chdir(tmp_path)

    merged, source_map = config_manager.load_cascade_with_sources(procedure)

    assert merged == {}
    assert source_map == {}


def test_load_cascade_with_sources_skips_empty_configs(tmp_path, config_manager, monkeypatch):
    system_config = tmp_path / "system.yml"
    user_config = tmp_path / "user.yml"
    root_config = tmp_path / ".tactus" / "config.yml"
    parent_config = tmp_path / "parent" / ".tactus" / "config.yml"
    local_config = tmp_path / "proc" / ".tactus" / "config.yml"
    sidecar_config = tmp_path / "proc" / "test.tac.yml"

    parent_config.parent.mkdir(parents=True)
    local_config.parent.mkdir(parents=True)
    root_config.parent.mkdir(parents=True)

    for path in [
        system_config,
        user_config,
        root_config,
        parent_config,
        local_config,
        sidecar_config,
    ]:
        path.write_text("noop: true")

    procedure = tmp_path / "proc" / "test.tac"
    procedure.write_text("-- test")

    monkeypatch.setattr(config_manager, "_get_system_config_paths", lambda: [system_config])
    monkeypatch.setattr(config_manager, "_get_user_config_paths", lambda: [user_config])
    monkeypatch.setattr(config_manager, "_find_directory_configs", lambda _path: [parent_config])
    monkeypatch.setattr(config_manager, "_load_yaml_file", lambda _path: {})
    monkeypatch.setattr(config_manager, "_load_from_environment", lambda: {})
    monkeypatch.chdir(tmp_path)

    merged, source_map = config_manager.load_cascade_with_sources(procedure)

    assert merged == {}
    assert source_map == {}


def test_load_cascade_with_sources_includes_all_sources(tmp_path, config_manager, monkeypatch):
    system_config = tmp_path / "system.yml"
    user_config = tmp_path / "user.yml"
    root_config = tmp_path / ".tactus" / "config.yml"
    parent_config = tmp_path / "parent" / ".tactus" / "config.yml"
    local_config = tmp_path / "proc" / ".tactus" / "config.yml"
    sidecar_config = tmp_path / "proc" / "test.tac.yml"

    parent_config.parent.mkdir(parents=True)
    local_config.parent.mkdir(parents=True)
    root_config.parent.mkdir(parents=True)

    system_config.write_text("system_flag: true")
    user_config.write_text("user_name: alice")
    root_config.write_text("root_key: root")
    parent_config.write_text("parent_key: parent")
    local_config.write_text("local_key: local")
    sidecar_config.write_text("sidecar_key: sidecar")

    procedure = tmp_path / "proc" / "test.tac"
    procedure.write_text("-- test")

    monkeypatch.setattr(config_manager, "_get_system_config_paths", lambda: [system_config])
    monkeypatch.setattr(config_manager, "_get_user_config_paths", lambda: [user_config])
    monkeypatch.setattr(config_manager, "_find_directory_configs", lambda _path: [parent_config])
    monkeypatch.setattr(config_manager, "_load_from_environment", lambda: {})
    monkeypatch.chdir(tmp_path)

    merged, source_map = config_manager.load_cascade_with_sources(procedure)

    assert merged["system_flag"] is True
    assert merged["user_name"] == "alice"
    assert merged["root_key"] == "root"
    assert merged["parent_key"] == "parent"
    assert merged["local_key"] == "local"
    assert merged["sidecar_key"] == "sidecar"
    assert source_map["sidecar_key"].source_type == "sidecar"


# ============================================================================
# Source Tracking Tests (Phase 2A)
# ============================================================================


class TestSourceTracking:
    """Tests for source tracking functionality in ConfigManager."""

    def test_config_value_dataclass(self):
        """Test ConfigValue dataclass structure and to_dict method."""
        cv = ConfigValue(
            value="test-value",
            source="user:/home/user/.tactus/config.yml",
            source_type="user",
            path="test.key",
            overridden_by=None,
            override_chain=[("user:/home/user/.tactus/config.yml", "test-value")],
            is_env_override=False,
            original_env_var=None,
        )

        assert cv.value == "test-value"
        assert cv.source_type == "user"
        assert cv.path == "test.key"
        assert not cv.is_env_override

        # Test to_dict
        d = cv.to_dict()
        assert d["value"] == "test-value"
        assert d["source_type"] == "user"
        assert d["path"] == "test.key"

    def test_load_cascade_with_sources_basic(self, tmp_path, config_manager, monkeypatch):
        """Test basic source tracking with load_cascade_with_sources."""
        # Create project config
        root_config = tmp_path / ".tactus"
        root_config.mkdir()
        (root_config / "config.yml").write_text(
            yaml.dump({"default_model": "gpt-4", "tool_paths": ["./tools"]})
        )

        # Create procedure
        procedure = tmp_path / "test.tac"
        procedure.write_text("-- Test")

        monkeypatch.chdir(tmp_path)

        config, source_map = config_manager.load_cascade_with_sources(procedure)

        # Check config
        assert config["default_model"] == "gpt-4"
        assert "tool_paths" in config

        # Check source map
        assert "default_model" in source_map
        assert source_map["default_model"].source_type == "project"
        assert source_map["default_model"].value == "gpt-4"

    def test_env_var_tracking(self, tmp_path, config_manager, monkeypatch):
        """Test that environment variables are properly tracked with var names."""
        # Set env var
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-123")

        # Create minimal project config
        root_config = tmp_path / ".tactus"
        root_config.mkdir()
        (root_config / "config.yml").write_text(yaml.dump({"default_model": "gpt-4"}))

        procedure = tmp_path / "test.tac"
        procedure.write_text("-- Test")

        monkeypatch.chdir(tmp_path)

        config, source_map = config_manager.load_cascade_with_sources(procedure)

        # Check that env var is tracked (now uses nested key format)
        assert "openai.api_key" in source_map
        cv = source_map["openai.api_key"]
        assert cv.source_type == "environment"
        assert cv.is_env_override is True
        assert cv.original_env_var == "OPENAI_API_KEY"
        assert cv.value == "sk-test-123"

    def test_override_chain_building(self, tmp_path, config_manager, monkeypatch):
        """Test that override chains are built correctly."""
        # Create user config
        user_config = tmp_path / ".tactus"
        user_config.mkdir()

        # Create project config with different value
        root_config = tmp_path / "project" / ".tactus"
        root_config.mkdir(parents=True)
        (root_config / "config.yml").write_text(
            yaml.dump({"default_model": "gpt-4", "temperature": 0.7})
        )

        procedure = tmp_path / "project" / "test.tac"
        procedure.write_text("-- Test")

        monkeypatch.chdir(tmp_path / "project")

        config, source_map = config_manager.load_cascade_with_sources(procedure)

        # Check override chain for default_model
        cv = source_map["default_model"]
        assert cv.value == "gpt-4"
        assert len(cv.override_chain) >= 1
        assert cv.override_chain[-1][1] == "gpt-4"  # Last override value

    def test_nested_config_tracking(self, tmp_path, config_manager, monkeypatch):
        """Test source tracking for nested configuration values."""
        root_config = tmp_path / ".tactus"
        root_config.mkdir()
        (root_config / "config.yml").write_text(
            yaml.dump(
                {
                    "aws": {
                        "region": "us-west-2",
                        "timeout": 30,
                    },
                    "ide": {
                        "theme": "dark",
                        "font_size": 14,
                    },
                }
            )
        )

        procedure = tmp_path / "test.tac"
        procedure.write_text("-- Test")

        monkeypatch.chdir(tmp_path)

        config, source_map = config_manager.load_cascade_with_sources(procedure)

        # Check nested values are tracked
        assert "aws.region" in source_map
        assert source_map["aws.region"].value == "us-west-2"
        assert source_map["aws.region"].source_type == "project"

        assert "aws.timeout" in source_map
        assert source_map["aws.timeout"].value == 30

        assert "ide.theme" in source_map
        assert source_map["ide.theme"].value == "dark"

    def test_list_merging_with_tracking(self, tmp_path, config_manager, monkeypatch):
        """Test that list merging is tracked correctly."""
        # Create two configs with lists
        root_config = tmp_path / ".tactus"
        root_config.mkdir()
        (root_config / "config.yml").write_text(yaml.dump({"tool_paths": ["./common", "./shared"]}))

        subdir = tmp_path / "sub"
        subdir.mkdir()
        procedure = subdir / "test.tac"
        procedure.write_text("-- Test")

        sidecar = subdir / "test.tac.yml"
        sidecar.write_text(yaml.dump({"tool_paths": ["./local", "./specific"]}))

        monkeypatch.chdir(tmp_path)

        config, source_map = config_manager.load_cascade_with_sources(procedure)

        # Check that lists were merged
        assert len(config["tool_paths"]) == 4
        assert "./common" in config["tool_paths"]
        assert "./local" in config["tool_paths"]

        # Check source tracking for list
        assert "tool_paths" in source_map
        cv = source_map["tool_paths"]
        assert cv.source_type == "sidecar"  # Last source
        assert len(cv.override_chain) >= 2  # At least root and sidecar

    def test_deep_merge_with_tracking_simple(self, config_manager):
        """Test _deep_merge_with_tracking with simple values."""
        base = {"key1": "value1", "key2": "value2"}
        override = {"key2": "new_value2", "key3": "value3"}

        result, source_map = config_manager._deep_merge_with_tracking(
            base, override, "source1", "source2", ""
        )

        # Check merge result
        assert result["key1"] == "value1"
        assert result["key2"] == "new_value2"
        assert result["key3"] == "value3"

        # Check source tracking
        assert "key2" in source_map
        assert source_map["key2"].value == "new_value2"
        assert source_map["key2"].source == "source2"

    def test_deep_merge_nested_dicts(self, config_manager):
        """Test deep merge with nested dictionaries."""
        base = {"aws": {"region": "us-east-1", "timeout": 30}}
        override = {"aws": {"region": "us-west-2", "retries": 3}}

        result, source_map = config_manager._deep_merge_with_tracking(
            base, override, "user:/path1", "project:/path2", ""
        )

        # Check merge result
        assert result["aws"]["region"] == "us-west-2"
        assert result["aws"]["timeout"] == 30
        assert result["aws"]["retries"] == 3

        # Check source tracking for nested values
        assert "aws.region" in source_map
        assert source_map["aws.region"].value == "us-west-2"
        assert source_map["aws.region"].source_type == "project"

        assert "aws.timeout" in source_map
        assert source_map["aws.timeout"].value == 30

    def test_extract_env_var_name(self, config_manager):
        """Test _extract_env_var_name helper."""
        assert (
            config_manager._extract_env_var_name("environment:OPENAI_API_KEY") == "OPENAI_API_KEY"
        )
        assert config_manager._extract_env_var_name("user:/path") is None
        assert config_manager._extract_env_var_name("environment:") == ""

    def test_env_var_mapping_populated(self, config_manager, monkeypatch):
        """Test that env_var_mapping is populated correctly."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.setenv("AWS_DEFAULT_REGION", "us-west-2")

        config_manager._load_from_environment()

        # Check mapping was populated (now uses nested key format for all)
        assert "openai.api_key" in config_manager.env_var_mapping
        assert config_manager.env_var_mapping["openai.api_key"] == "OPENAI_API_KEY"
        assert "aws.default_region" in config_manager.env_var_mapping
        assert config_manager.env_var_mapping["aws.default_region"] == "AWS_DEFAULT_REGION"

    def test_track_nested_values_dict(self, config_manager):
        """Test _track_nested_values with dictionary."""
        obj = {"key1": "value1", "nested": {"key2": "value2"}}
        source_map = {}

        config_manager._track_nested_values(obj, "test_source", "project", "root", source_map)

        assert "root.key1" in source_map
        assert source_map["root.key1"].value == "value1"
        assert "root.nested.key2" in source_map
        assert source_map["root.nested.key2"].value == "value2"

    def test_track_nested_values_list(self, config_manager):
        """Test _track_nested_values with list."""
        obj = ["item1", "item2", "item3"]
        source_map = {}

        config_manager._track_nested_values(obj, "test_source", "project", "mylist", source_map)

        assert "mylist[0]" in source_map
        assert source_map["mylist[0]"].value == "item1"
        assert "mylist[1]" in source_map
        assert source_map["mylist[1]"].value == "item2"

    def test_backward_compatibility(self, tmp_path, config_manager, monkeypatch):
        """Test that existing load_cascade() still works (backward compatibility)."""
        root_config = tmp_path / ".tactus"
        root_config.mkdir()
        (root_config / "config.yml").write_text(
            yaml.dump({"default_model": "gpt-4", "tool_paths": ["./tools"]})
        )

        procedure = tmp_path / "test.tac"
        procedure.write_text("-- Test")

        monkeypatch.chdir(tmp_path)

        # Old method should still work
        config = config_manager.load_cascade(procedure)
        assert config["default_model"] == "gpt-4"
        assert "tool_paths" in config

    def test_env_override_of_file_config(self, tmp_path, config_manager, monkeypatch):
        """Test env var overriding file-based config."""
        # Set env var
        monkeypatch.setenv("OPENAI_API_KEY", "sk-env-key")

        # Create config file with different value
        root_config = tmp_path / ".tactus"
        root_config.mkdir()
        (root_config / "config.yml").write_text(yaml.dump({"openai": {"api_key": "sk-file-key"}}))

        procedure = tmp_path / "test.tac"
        procedure.write_text("-- Test")

        monkeypatch.chdir(tmp_path)

        config, source_map = config_manager.load_cascade_with_sources(procedure)

        # Env var should win - both now use nested key format (openai.api_key)
        # The env loader creates openai.api_key (nested)
        # The file also has openai.api_key (nested)
        # Env var has higher priority and overrides file config
        assert "openai.api_key" in source_map
        cv = source_map["openai.api_key"]
        assert cv.is_env_override is True
        assert cv.original_env_var == "OPENAI_API_KEY"
        assert cv.value == "sk-env-key"
        # Override chain should show the file value was overridden
        assert len(cv.override_chain) >= 2  # At least file and env

    def test_multiple_override_chain(self, tmp_path, config_manager, monkeypatch):
        """Test override chain with multiple config sources."""
        # Set env var (lowest)
        monkeypatch.setenv("OPENAI_API_KEY", "sk-env")

        # Create user config
        user_config_dir = tmp_path / "user" / ".tactus"
        user_config_dir.mkdir(parents=True)

        # Create project config
        project_dir = tmp_path / "project"
        project_config = project_dir / ".tactus"
        project_config.mkdir(parents=True)
        (project_config / "config.yml").write_text(yaml.dump({"default_model": "gpt-3.5"}))

        # Create sidecar (highest)
        procedure = project_dir / "test.tac"
        procedure.write_text("-- Test")
        sidecar = project_dir / "test.tac.yml"
        sidecar.write_text(yaml.dump({"default_model": "gpt-4"}))

        monkeypatch.chdir(project_dir)

        config, source_map = config_manager.load_cascade_with_sources(procedure)

        # Check final value
        assert config["default_model"] == "gpt-4"

        # Check override chain
        cv = source_map["default_model"]
        assert cv.source_type == "sidecar"
        assert len(cv.override_chain) >= 1
