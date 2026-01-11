"""
Configuration Manager for Tactus.

Implements cascading configuration from multiple sources with clear priority ordering.
"""

import logging
import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from copy import deepcopy
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ConfigValue:
    """
    Represents a configuration value with source tracking metadata.

    This class wraps config values with information about where they came from
    and how they were overridden through the cascade system.
    """

    value: Any
    """The actual configuration value"""

    source: str
    """Source identifier (e.g., 'user:/path/to/config.yml', 'environment:OPENAI_API_KEY')"""

    source_type: str
    """Normalized source type: 'system', 'user', 'project', 'parent', 'local', 'sidecar', 'environment'"""

    path: str
    """Config path (e.g., 'aws.region', 'ide.theme')"""

    overridden_by: Optional[str] = None
    """If overridden, what source did the override? None if this is the final value."""

    override_chain: List[Tuple[str, Any]] = field(default_factory=list)
    """History of overrides: [(source, value), ...] in chronological order"""

    is_env_override: bool = False
    """True if currently overridden by an environment variable"""

    original_env_var: Optional[str] = None
    """Original environment variable name if value came from env (e.g., 'OPENAI_API_KEY')"""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "value": self.value,
            "source": self.source,
            "source_type": self.source_type,
            "path": self.path,
            "overridden_by": self.overridden_by,
            "override_chain": self.override_chain,
            "is_env_override": self.is_env_override,
            "original_env_var": self.original_env_var,
        }


class ConfigManager:
    """
    Manages configuration loading and merging from multiple sources.

    Priority order (highest to lowest):
    1. CLI arguments (handled by caller)
    2. Sidecar config (procedure.tac.yml)
    3. Local directory config (.tactus/config.yml in procedure's directory)
    4. Parent directory configs (walk up tree)
    5. Project config (.tactus/config.yml in cwd)
    6. User config (~/.tactus/config.yml, or XDG config dir)
    7. System config (/etc/tactus/config.yml, etc.)
    8. Environment variables (fallback)
    """

    def __init__(self):
        """Initialize configuration manager."""
        self.loaded_configs = []  # Track loaded configs for debugging
        self.env_var_mapping = {}  # Track which env var each config key came from

    def load_cascade(self, procedure_path: Path) -> Dict[str, Any]:
        """
        Load and merge all configuration sources in priority order.

        Priority order (lowest to highest):
        System → User → Project → Parent → Local → Environment → Sidecar → CLI

        Args:
            procedure_path: Path to the .tac procedure file

        Returns:
            Merged configuration dictionary
        """
        configs = []

        # 1. System config (lowest precedence)
        for system_path in self._get_system_config_paths():
            if system_path.exists():
                system_config = self._load_yaml_file(system_path)
                if system_config:
                    configs.append((f"system:{system_path}", system_config))
                    logger.debug(f"Loaded system config: {system_path}")

        # 2. User config (~/.tactus/config.yml, XDG, etc.)
        for user_path in self._get_user_config_paths():
            if user_path.exists():
                user_config = self._load_yaml_file(user_path)
                if user_config:
                    configs.append((f"user:{user_path}", user_config))
                    logger.debug(f"Loaded user config: {user_path}")

        # 3. Project config (.tactus/config.yml in cwd)
        root_config_path = Path.cwd() / ".tactus" / "config.yml"
        if root_config_path.exists():
            root_config = self._load_yaml_file(root_config_path)
            if root_config:
                configs.append(("root", root_config))
                logger.debug(f"Loaded root config: {root_config_path}")

        # 4. Parent directory configs (walk up from procedure directory)
        procedure_dir = procedure_path.parent.resolve()
        parent_configs = self._find_directory_configs(procedure_dir)
        for config_path in parent_configs:
            config = self._load_yaml_file(config_path)
            if config:
                configs.append((f"parent:{config_path}", config))
                logger.debug(f"Loaded parent config: {config_path}")

        # 5. Local directory config (.tactus/config.yml in procedure's directory)
        local_config_path = procedure_dir / ".tactus" / "config.yml"
        if local_config_path.exists() and local_config_path not in parent_configs:
            local_config = self._load_yaml_file(local_config_path)
            if local_config:
                configs.append(("local", local_config))
                logger.debug(f"Loaded local config: {local_config_path}")

        # 6. Environment variables (override config files)
        env_config = self._load_from_environment()
        if env_config:
            configs.append(("environment", env_config))
            logger.debug("Loaded config from environment variables")

        # 7. Sidecar config (highest priority, except CLI args)
        sidecar_path = self._find_sidecar_config(procedure_path)
        if sidecar_path:
            sidecar_config = self._load_yaml_file(sidecar_path)
            if sidecar_config:
                configs.append(("sidecar", sidecar_config))
                logger.debug(f"Loaded sidecar config: {sidecar_path}")

        # Store for debugging
        self.loaded_configs = configs

        # Merge all configs (later configs override earlier ones)
        merged = self._merge_configs([c[1] for c in configs])

        logger.debug(f"Merged configuration from {len(configs)} source(s)")
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

        Also populates self.env_var_mapping to track which env var each config key came from.

        Returns:
            Configuration dictionary from environment
        """
        config = {}

        # Load known config keys from environment
        # NOTE: Keys must match the config file structure (nested under provider name)
        env_mappings = {
            "OPENAI_API_KEY": ("openai", "api_key"),
            "GOOGLE_API_KEY": ("google", "api_key"),
            "AWS_ACCESS_KEY_ID": ("aws", "access_key_id"),
            "AWS_SECRET_ACCESS_KEY": ("aws", "secret_access_key"),
            "AWS_DEFAULT_REGION": ("aws", "default_region"),
            "AWS_PROFILE": ("aws", "profile"),
            "TOOL_PATHS": "tool_paths",
            # Sandbox configuration
            "TACTUS_SANDBOX_ENABLED": ("sandbox", "enabled"),
            "TACTUS_SANDBOX_IMAGE": ("sandbox", "image"),
        }

        # Boolean env vars that need special parsing
        boolean_env_keys = {"TACTUS_SANDBOX_ENABLED"}

        for env_key, config_key in env_mappings.items():
            value = os.environ.get(env_key)
            if value:
                # Parse boolean values
                if env_key in boolean_env_keys:
                    value = value.lower() in ("true", "1", "yes", "on")

                if isinstance(config_key, tuple):
                    # Nested key (e.g., aws.access_key_id, sandbox.enabled)
                    if config_key[0] not in config:
                        config[config_key[0]] = {}
                    config[config_key[0]][config_key[1]] = value
                    # Track env var name for this nested key
                    path = f"{config_key[0]}.{config_key[1]}"
                    self.env_var_mapping[path] = env_key
                elif config_key == "tool_paths":
                    # Parse JSON list
                    import json

                    try:
                        config[config_key] = json.loads(value)
                        self.env_var_mapping[config_key] = env_key
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse TOOL_PATHS as JSON: {value}")
                else:
                    config[config_key] = value
                    self.env_var_mapping[config_key] = env_key

        return config

    def _get_system_config_paths(self) -> List[Path]:
        """
        Return system-wide config locations (lowest precedence).

        These are optional; most users will rely on user-wide or project configs.
        """
        if os.name == "nt":
            program_data = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData"))
            return [program_data / "tactus" / "config.yml"]

        return [
            Path("/etc/tactus/config.yml"),
            Path("/usr/local/etc/tactus/config.yml"),
        ]

    def _get_user_config_paths(self) -> List[Path]:
        """
        Return per-user config locations (lower precedence than project configs).

        Order is from lower to higher precedence so later configs override earlier ones.
        """
        paths: List[Path] = []

        xdg_home = os.environ.get("XDG_CONFIG_HOME")
        if xdg_home:
            paths.append(Path(xdg_home) / "tactus" / "config.yml")
        else:
            paths.append(Path.home() / ".config" / "tactus" / "config.yml")

        # Legacy / explicit location (documented by this project)
        paths.append(Path.home() / ".tactus" / "config.yml")

        # Deduplicate while preserving order
        seen = set()
        unique: List[Path] = []
        for p in paths:
            if p not in seen:
                unique.append(p)
                seen.add(p)
        return unique

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

    def _deep_merge_with_tracking(
        self,
        base: Dict[str, Any],
        override: Dict[str, Any],
        base_source: str,
        override_source: str,
        path_prefix: str = "",
        base_source_map: Optional[Dict[str, ConfigValue]] = None,
    ) -> Tuple[Dict[str, Any], Dict[str, ConfigValue]]:
        """
        Deep merge with source tracking at every level.

        This method performs the same merge logic as _deep_merge() but also
        tracks where each value came from and builds a complete override chain.

        Args:
            base: Base dictionary
            override: Override dictionary (takes precedence)
            base_source: Source identifier for base config
            override_source: Source identifier for override config
            path_prefix: Current path prefix for nested keys
            base_source_map: Existing source map from base (for nested merges)

        Returns:
            Tuple of (merged_dict, source_map)
            - merged_dict: The merged configuration
            - source_map: Dict mapping paths to ConfigValue objects
        """
        result = deepcopy(base)
        source_map: Dict[str, ConfigValue] = base_source_map.copy() if base_source_map else {}

        # Normalize source types
        base_source_type = base_source.split(":")[0] if ":" in base_source else base_source
        override_source_type = (
            override_source.split(":")[0] if ":" in override_source else override_source
        )

        for key, value in override.items():
            current_path = f"{path_prefix}.{key}" if path_prefix else key

            if key in result:
                base_value = result[key]

                # If both are dicts, deep merge recursively with tracking
                if isinstance(base_value, dict) and isinstance(value, dict):
                    # Get nested source map for base
                    nested_base_source_map = {
                        k: v for k, v in source_map.items() if k.startswith(current_path + ".")
                    }

                    # Ensure all base dict values are tracked before merge
                    # This handles cases where base dict has values that aren't yet tracked
                    # Use overwrite=False to preserve existing source info from earlier merges
                    self._track_nested_values(
                        base_value,
                        base_source,
                        base_source_type,
                        current_path,
                        nested_base_source_map,
                        overwrite=False,
                    )

                    merged_dict, nested_source_map = self._deep_merge_with_tracking(
                        base_value,
                        value,
                        base_source,
                        override_source,
                        current_path,
                        nested_base_source_map,
                    )
                    result[key] = merged_dict

                    # Update source map with nested results
                    source_map.update(nested_source_map)

                    # Track the dict itself
                    if current_path in source_map:
                        # Build override chain
                        override_chain = source_map[current_path].override_chain.copy()
                        override_chain.append((override_source, value))
                    else:
                        override_chain = [(base_source, base_value), (override_source, value)]

                    # Get env var name if from environment
                    env_var_name = None
                    if override_source_type == "environment":
                        env_var_name = self.env_var_mapping.get(current_path)

                    source_map[current_path] = ConfigValue(
                        value=merged_dict,
                        source=override_source,
                        source_type=override_source_type,
                        path=current_path,
                        overridden_by=None,  # Final value
                        override_chain=override_chain,
                        is_env_override=(override_source_type == "environment"),
                        original_env_var=env_var_name,
                    )

                # If both are lists, extend (combine)
                elif isinstance(base_value, list) and isinstance(value, list):
                    # Combine lists, removing duplicates while preserving order
                    combined = base_value.copy()
                    for item in value:
                        if item not in combined:
                            combined.append(item)
                    result[key] = combined

                    # Track list override
                    if current_path in source_map:
                        override_chain = source_map[current_path].override_chain.copy()
                        override_chain.append((override_source, value))
                    else:
                        override_chain = [(base_source, base_value), (override_source, value)]

                    # Get env var name if from environment
                    env_var_name = None
                    if override_source_type == "environment":
                        env_var_name = self.env_var_mapping.get(current_path)

                    source_map[current_path] = ConfigValue(
                        value=combined,
                        source=override_source,
                        source_type=override_source_type,
                        path=current_path,
                        overridden_by=None,
                        override_chain=override_chain,
                        is_env_override=(override_source_type == "environment"),
                        original_env_var=env_var_name,
                    )

                # Otherwise, override takes precedence
                else:
                    result[key] = deepcopy(value)

                    # Track simple value override
                    if current_path in source_map:
                        override_chain = source_map[current_path].override_chain.copy()
                        override_chain.append((override_source, value))
                    else:
                        override_chain = [(base_source, base_value), (override_source, value)]

                    # Get env var name if from environment
                    env_var_name = None
                    if override_source_type == "environment":
                        env_var_name = self.env_var_mapping.get(current_path)

                    source_map[current_path] = ConfigValue(
                        value=value,
                        source=override_source,
                        source_type=override_source_type,
                        path=current_path,
                        overridden_by=None,
                        override_chain=override_chain,
                        is_env_override=(override_source_type == "environment"),
                        original_env_var=env_var_name,
                    )
            else:
                # New key, not an override
                result[key] = deepcopy(value)

                # Get env var name if from environment
                env_var_name = None
                if override_source_type == "environment":
                    env_var_name = self.env_var_mapping.get(current_path)

                # Track as new value
                source_map[current_path] = ConfigValue(
                    value=value,
                    source=override_source,
                    source_type=override_source_type,
                    path=current_path,
                    overridden_by=None,
                    override_chain=[(override_source, value)],
                    is_env_override=(override_source_type == "environment"),
                    original_env_var=env_var_name,
                )

                # For nested dicts/lists in new keys, track their children
                if isinstance(value, dict):
                    self._track_nested_values(
                        value, override_source, override_source_type, current_path, source_map
                    )

        return result, source_map

    def _track_nested_values(
        self,
        obj: Any,
        source: str,
        source_type: str,
        path_prefix: str,
        source_map: Dict[str, ConfigValue],
        overwrite: bool = True,
    ) -> None:
        """
        Recursively track nested values in dicts and lists.

        This is used to populate source_map for values that don't have overrides.

        Args:
            obj: The object to track values from
            source: Source identifier (e.g., "user:/path" or "environment")
            source_type: Normalized type (e.g., "user", "environment")
            path_prefix: Current path prefix for nested keys
            source_map: Dict to populate with ConfigValue entries
            overwrite: If False, won't overwrite existing source_map entries
        """
        if isinstance(obj, dict):
            for key, value in obj.items():
                current_path = f"{path_prefix}.{key}" if path_prefix else key

                # Skip if we shouldn't overwrite and already have source info
                if not overwrite and current_path in source_map:
                    # Still recurse for nested structures
                    if isinstance(value, (dict, list)):
                        self._track_nested_values(
                            value, source, source_type, current_path, source_map, overwrite
                        )
                    continue

                # For environment variables, look up the specific env var name
                env_var_name = None
                if source_type == "environment" and current_path in self.env_var_mapping:
                    env_var_name = self.env_var_mapping[current_path]
                    # Update source to include env var name
                    effective_source = f"environment:{env_var_name}"
                else:
                    effective_source = source

                source_map[current_path] = ConfigValue(
                    value=value,
                    source=effective_source,
                    source_type=source_type,
                    path=current_path,
                    overridden_by=None,
                    override_chain=[(effective_source, value)],
                    is_env_override=(source_type == "environment"),
                    original_env_var=env_var_name,
                )
                if isinstance(value, (dict, list)):
                    self._track_nested_values(
                        value, source, source_type, current_path, source_map, overwrite
                    )
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                current_path = f"{path_prefix}[{i}]"
                # Skip if we shouldn't overwrite and already have source info
                if not overwrite and current_path in source_map:
                    # Still recurse for nested structures
                    if isinstance(item, (dict, list)):
                        self._track_nested_values(
                            item, source, source_type, current_path, source_map, overwrite
                        )
                    continue

                source_map[current_path] = ConfigValue(
                    value=item,
                    source=source,
                    source_type=source_type,
                    path=current_path,
                    overridden_by=None,
                    override_chain=[(source, item)],
                    is_env_override=(source_type == "environment"),
                    original_env_var=None,  # List items don't have individual env vars
                )
                if isinstance(item, (dict, list)):
                    self._track_nested_values(
                        item, source, source_type, current_path, source_map, overwrite
                    )

    def _extract_env_var_name(self, source: str) -> Optional[str]:
        """
        Extract environment variable name from source string.

        Args:
            source: Source identifier like "environment:OPENAI_API_KEY"

        Returns:
            Environment variable name or None if not an env source
        """
        if source.startswith("environment:"):
            return source.split(":", 1)[1]
        return None

    def load_cascade_with_sources(
        self, procedure_path: Path
    ) -> Tuple[Dict[str, Any], Dict[str, ConfigValue]]:
        """
        Load cascade and return both merged config and detailed source map.

        This is the enhanced version of load_cascade() that provides complete
        transparency into where each configuration value came from.

        Priority order (lowest to highest):
        System → User → Project → Parent → Local → Environment → Sidecar → CLI

        Args:
            procedure_path: Path to the .tac procedure file

        Returns:
            Tuple of (merged_config, source_map)
            - merged_config: Traditional flat merged config (backward compatible)
            - source_map: Dict mapping paths to ConfigValue objects with full metadata
        """
        configs = []

        # 1. System config (lowest precedence)
        for system_path in self._get_system_config_paths():
            if system_path.exists():
                system_config = self._load_yaml_file(system_path)
                if system_config:
                    configs.append((f"system:{system_path}", system_config))
                    logger.debug(f"Loaded system config: {system_path}")

        # 2. User config (~/.tactus/config.yml, XDG, etc.)
        for user_path in self._get_user_config_paths():
            if user_path.exists():
                user_config = self._load_yaml_file(user_path)
                if user_config:
                    configs.append((f"user:{user_path}", user_config))
                    logger.debug(f"Loaded user config: {user_path}")

        # 3. Project config (.tactus/config.yml in cwd)
        root_config_path = Path.cwd() / ".tactus" / "config.yml"
        if root_config_path.exists():
            root_config = self._load_yaml_file(root_config_path)
            if root_config:
                configs.append((f"project:{root_config_path}", root_config))
                logger.debug(f"Loaded root config: {root_config_path}")

        # 4. Parent directory configs (walk up from procedure directory)
        procedure_dir = procedure_path.parent.resolve()
        parent_configs = self._find_directory_configs(procedure_dir)
        for config_path in parent_configs:
            config = self._load_yaml_file(config_path)
            if config:
                configs.append((f"parent:{config_path}", config))
                logger.debug(f"Loaded parent config: {config_path}")

        # 5. Local directory config (.tactus/config.yml in procedure's directory)
        local_config_path = procedure_dir / ".tactus" / "config.yml"
        if (
            local_config_path.exists()
            and local_config_path not in [root_config_path] + parent_configs
        ):
            local_config = self._load_yaml_file(local_config_path)
            if local_config:
                configs.append((f"local:{local_config_path}", local_config))
                logger.debug(f"Loaded local config: {local_config_path}")

        # 6. Environment variables (override config files)
        env_config = self._load_from_environment()
        if env_config:
            # We use "environment" as source, but individual var names are in self.env_var_mapping
            configs.append(("environment", env_config))
            logger.debug(
                f"Loaded config from environment variables: {list(self.env_var_mapping.keys())}"
            )

        # 7. Sidecar config (highest priority, except CLI args)
        sidecar_path = self._find_sidecar_config(procedure_path)
        if sidecar_path:
            sidecar_config = self._load_yaml_file(sidecar_path)
            if sidecar_config:
                configs.append((f"sidecar:{sidecar_path}", sidecar_config))
                logger.info(f"Loaded sidecar config: {sidecar_path}")

        # Store for debugging
        self.loaded_configs = configs

        # Merge all configs with source tracking
        if not configs:
            return {}, {}

        # Start with first config
        source, config = configs[0]
        result = deepcopy(config)
        source_map: Dict[str, ConfigValue] = {}

        # Track initial values
        self._track_nested_values(config, source, source.split(":")[0], "", source_map)

        # Merge remaining configs with tracking
        for source, config in configs[1:]:
            result, source_map = self._deep_merge_with_tracking(
                result, config, "merged", source, "", source_map
            )

        logger.info(f"Merged configuration from {len(configs)} source(s) with full tracking")
        return result, source_map
