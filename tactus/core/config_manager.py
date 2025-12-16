"""
Configuration Manager for Tactus.

Implements cascading configuration from multiple sources with clear priority ordering.
"""

import logging
import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List
from copy import deepcopy

logger = logging.getLogger(__name__)


class ConfigManager:
    """
    Manages configuration loading and merging from multiple sources.

    Priority order (highest to lowest):
    1. CLI arguments (handled by caller)
    2. Sidecar config (procedure.tac.yml)
    3. Local directory config (.tactus/config.yml in procedure's directory)
    4. Parent directory configs (walk up tree)
    5. Root config (.tactus/config.yml in cwd)
    6. Environment variables (fallback)
    """

    def __init__(self):
        """Initialize configuration manager."""
        self.loaded_configs = []  # Track loaded configs for debugging

    def load_cascade(self, procedure_path: Path) -> Dict[str, Any]:
        """
        Load and merge all configuration sources in priority order.

        Args:
            procedure_path: Path to the .tac procedure file

        Returns:
            Merged configuration dictionary
        """
        configs = []

        # 1. Environment variables (lowest priority)
        env_config = self._load_from_environment()
        if env_config:
            configs.append(("environment", env_config))
            logger.debug("Loaded config from environment variables")

        # 2. Root config (.tactus/config.yml in cwd)
        root_config_path = Path.cwd() / ".tactus" / "config.yml"
        if root_config_path.exists():
            root_config = self._load_yaml_file(root_config_path)
            if root_config:
                configs.append(("root", root_config))
                logger.debug(f"Loaded root config: {root_config_path}")

        # 3. Parent directory configs (walk up from procedure directory)
        procedure_dir = procedure_path.parent.resolve()
        parent_configs = self._find_directory_configs(procedure_dir)
        for config_path in parent_configs:
            config = self._load_yaml_file(config_path)
            if config:
                configs.append((f"parent:{config_path}", config))
                logger.debug(f"Loaded parent config: {config_path}")

        # 4. Local directory config (.tactus/config.yml in procedure's directory)
        local_config_path = procedure_dir / ".tactus" / "config.yml"
        if local_config_path.exists() and local_config_path not in parent_configs:
            local_config = self._load_yaml_file(local_config_path)
            if local_config:
                configs.append(("local", local_config))
                logger.debug(f"Loaded local config: {local_config_path}")

        # 5. Sidecar config (highest priority, except CLI args)
        sidecar_path = self._find_sidecar_config(procedure_path)
        if sidecar_path:
            sidecar_config = self._load_yaml_file(sidecar_path)
            if sidecar_config:
                configs.append(("sidecar", sidecar_config))
                logger.info(f"Loaded sidecar config: {sidecar_path}")

        # Store for debugging
        self.loaded_configs = configs

        # Merge all configs (later configs override earlier ones)
        merged = self._merge_configs([c[1] for c in configs])

        logger.info(f"Merged configuration from {len(configs)} source(s)")
        return merged

    def _find_sidecar_config(self, tac_path: Path) -> Optional[Path]:
        """
        Find sidecar configuration file for a .tac procedure.

        Search order:
        1. {procedure}.tac.yml (exact match with .tac extension)
        2. {procedure}.yml (without .tac)

        Args:
            tac_path: Path to the .tac file

        Returns:
            Path to sidecar config if found, None otherwise
        """
        # Try .tac.yml first (preferred)
        sidecar_with_tac = tac_path.parent / f"{tac_path.name}.yml"
        if sidecar_with_tac.exists():
            return sidecar_with_tac

        # Try .yml (replace .tac extension)
        if tac_path.suffix == ".tac":
            sidecar_without_tac = tac_path.with_suffix(".yml")
            if sidecar_without_tac.exists():
                return sidecar_without_tac

        return None

    def _find_directory_configs(self, start_path: Path) -> List[Path]:
        """
        Walk up directory tree to find all .tactus/config.yml files.

        Args:
            start_path: Starting directory path

        Returns:
            List of config file paths (from root to start_path)
        """
        configs = []
        current = start_path.resolve()
        cwd = Path.cwd().resolve()

        # Walk up until we reach cwd or root
        while current != current.parent:
            # Skip if we've reached cwd (handled separately as root config)
            if current == cwd:
                break

            config_path = current / ".tactus" / "config.yml"
            if config_path.exists():
                configs.append(config_path)

            current = current.parent

        # Return in order from root to start_path (so later ones override)
        return list(reversed(configs))

    def _load_yaml_file(self, path: Path) -> Optional[Dict[str, Any]]:
        """
        Load YAML configuration file.

        Args:
            path: Path to YAML file

        Returns:
            Configuration dictionary or None if loading fails
        """
        try:
            with open(path, "r") as f:
                config = yaml.safe_load(f)
                return config if isinstance(config, dict) else {}
        except Exception as e:
            logger.warning(f"Failed to load config from {path}: {e}")
            return None

    def _load_from_environment(self) -> Dict[str, Any]:
        """
        Load configuration from environment variables.

        Returns:
            Configuration dictionary from environment
        """
        config = {}

        # Load known config keys from environment
        env_mappings = {
            "OPENAI_API_KEY": "openai_api_key",
            "AWS_ACCESS_KEY_ID": ("aws", "access_key_id"),
            "AWS_SECRET_ACCESS_KEY": ("aws", "secret_access_key"),
            "AWS_DEFAULT_REGION": ("aws", "default_region"),
            "TOOL_PATHS": "tool_paths",
        }

        for env_key, config_key in env_mappings.items():
            value = os.environ.get(env_key)
            if value:
                if isinstance(config_key, tuple):
                    # Nested key (e.g., aws.access_key_id)
                    if config_key[0] not in config:
                        config[config_key[0]] = {}
                    config[config_key[0]][config_key[1]] = value
                elif config_key == "tool_paths":
                    # Parse JSON list
                    import json

                    try:
                        config[config_key] = json.loads(value)
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse TOOL_PATHS as JSON: {value}")
                else:
                    config[config_key] = value

        return config

    def _merge_configs(self, configs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Deep merge multiple configuration dictionaries.

        Later configs override earlier ones.
        Lists are extended (combined) by default.
        Dicts are deep merged.

        Args:
            configs: List of config dicts to merge (in priority order)

        Returns:
            Merged configuration dictionary
        """
        if not configs:
            return {}

        result = {}

        for config in configs:
            result = self._deep_merge(result, config)

        return result

    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deep merge two dictionaries.

        Args:
            base: Base dictionary
            override: Override dictionary (takes precedence)

        Returns:
            Merged dictionary
        """
        result = deepcopy(base)

        for key, value in override.items():
            if key in result:
                base_value = result[key]

                # If both are dicts, deep merge
                if isinstance(base_value, dict) and isinstance(value, dict):
                    result[key] = self._deep_merge(base_value, value)

                # If both are lists, extend (combine)
                elif isinstance(base_value, list) and isinstance(value, list):
                    # Combine lists, removing duplicates while preserving order
                    combined = base_value.copy()
                    for item in value:
                        if item not in combined:
                            combined.append(item)
                    result[key] = combined

                # Otherwise, override takes precedence
                else:
                    result[key] = deepcopy(value)
            else:
                result[key] = deepcopy(value)

        return result
