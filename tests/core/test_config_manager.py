"""
Tests for the configuration manager and cascade system.
"""

import pytest
import yaml
from tactus.core.config_manager import ConfigManager


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

    assert env_config["openai_api_key"] == "test-key"
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
