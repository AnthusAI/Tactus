"""
Configuration API endpoints for Tactus IDE.

Provides RESTful API for loading and saving configuration files,
with support for the configuration cascade system.
"""

import logging
import shutil
import yaml
from pathlib import Path
from flask import Blueprint, request, jsonify
from typing import Dict, Any, List, Tuple, Optional

logger = logging.getLogger(__name__)

config_bp = Blueprint("config", __name__, url_prefix="/api/config")


def build_cascade_map(loaded_configs: List[Tuple[str, Dict[str, Any]]]) -> Dict[str, str]:
    """
    Build a map of config path -> source for cascade visualization.

    Args:
        loaded_configs: List of (source_name, config_dict) tuples

    Returns:
        Dictionary mapping config paths to their source
    """
    cascade_map = {}

    def add_paths(obj: Any, prefix: str = "", source: str = ""):
        """Recursively add paths from nested config structure."""
        if isinstance(obj, dict):
            for key, value in obj.items():
                path = f"{prefix}.{key}" if prefix else key
                cascade_map[path] = source
                add_paths(value, path, source)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                path = f"{prefix}[{i}]"
                add_paths(item, path, source)

    # Process configs in order (later ones override)
    for source, config in loaded_configs:
        # Extract simple source name (e.g., "user" from "user:/path/to/config.yml")
        source_name = source.split(":")[0] if ":" in source else source
        add_paths(config, "", source_name)

    return cascade_map


def load_yaml_file(path: Path) -> Optional[Dict[str, Any]]:
    """
    Load YAML file safely.

    Args:
        path: Path to YAML file

    Returns:
        Configuration dictionary or None if file doesn't exist or fails to load
    """
    if not path.exists():
        return None

    try:
        with open(path, "r") as f:
            config = yaml.safe_load(f)
            return config if isinstance(config, dict) else {}
    except Exception as e:
        logger.warning(f"Failed to load config from {path}: {e}")
        return None


def save_yaml_file(path: Path, config: Dict[str, Any], create_backup: bool = True):
    """
    Save configuration to YAML file.

    Args:
        path: Path to save config
        config: Configuration dictionary
        create_backup: Whether to create backup of existing file
    """
    # Create .tactus directory if needed
    path.parent.mkdir(parents=True, exist_ok=True)

    # Create backup if requested and file exists
    if create_backup and path.exists():
        backup_path = path.with_suffix(".yml.bak")
        shutil.copy2(path, backup_path)
        logger.info(f"Created backup: {backup_path}")

    # Save config
    with open(path, "w") as f:
        yaml.safe_dump(
            config,
            f,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
            indent=2,
        )

    logger.info(f"Saved config to: {path}")


@config_bp.route("", methods=["GET"])
def get_config():
    """
    Get configuration with cascade information.

    Returns:
        JSON response with:
        - config: Merged effective configuration
        - project_config: Project .tactus/config.yml
        - user_config: User ~/.tactus/config.yml
        - system_config: System config if exists
        - cascade: Map of config paths to their source (legacy)
        - source_details: Detailed source tracking with override chains
        - writable_configs: Which configs can be edited
        - config_paths: Full paths to all config files
    """
    try:
        from tactus.core.config_manager import ConfigManager

        # Create config manager
        config_manager = ConfigManager()

        # For IDE purposes, we load config without a specific procedure
        # Use a dummy path to trigger the cascade from project/user/system
        dummy_path = Path.cwd() / "dummy.tac"

        # Load cascade with source tracking
        effective_config, source_map = config_manager.load_cascade_with_sources(dummy_path)

        # Build legacy cascade map from loaded configs (for backward compatibility)
        cascade_map = build_cascade_map(config_manager.loaded_configs)

        # Convert source_map to JSON-serializable format
        source_details = {path: config_value.to_dict() for path, config_value in source_map.items()}

        # Load individual config files for editing
        project_config_path = Path.cwd() / ".tactus" / "config.yml"
        project_config = load_yaml_file(project_config_path)

        # Check if we should initialize from example template
        # This happens when:
        # 1. No config.yml exists, OR
        # 2. Config exists but has no API keys configured (openai_api_key is empty/missing)
        should_initialize_from_example = False

        if project_config is None:
            should_initialize_from_example = True
        elif isinstance(project_config, dict):
            # Check if API keys are configured
            # Support both old flat format (openai_api_key) and new nested format (openai.api_key)
            openai_key = None
            if "openai" in project_config and isinstance(project_config["openai"], dict):
                openai_key = project_config["openai"].get("api_key")
            else:
                openai_key = project_config.get("openai_api_key")

            aws_key = None
            if "aws" in project_config and isinstance(project_config["aws"], dict):
                aws_key = project_config["aws"].get("profile") or project_config["aws"].get(
                    "access_key_id"
                )
            else:
                aws_key = project_config.get("aws_access_key_id")

            google_key = None
            if "google" in project_config and isinstance(project_config["google"], dict):
                google_key = project_config["google"].get("api_key")

            # Check if keys are present and not placeholder values
            # Empty strings or None mean not configured
            has_openai_key = (
                openai_key
                and str(openai_key).strip() != ""
                and not str(openai_key).startswith("your-")
            )
            has_aws_keys = (
                aws_key
                and str(aws_key).strip() != ""
                and str(aws_key) != "default"
                and not str(aws_key).startswith("your-")
            )
            has_google_key = (
                google_key
                and str(google_key).strip() != ""
                and not str(google_key).startswith("your-")
            )

            # If no API keys are configured, initialize from example
            if not has_openai_key and not has_aws_keys and not has_google_key:
                should_initialize_from_example = True
        else:
            project_config = {}

        if should_initialize_from_example:
            example_config_path = Path.cwd() / ".tactus" / "config.yml.example"
            if example_config_path.exists():
                example_config = load_yaml_file(example_config_path) or {}
                # Merge with existing config (keeps existing values, adds missing fields from example)
                if project_config and isinstance(project_config, dict):
                    # Deep merge: example provides defaults, existing values are kept
                    merged_config = {**example_config, **project_config}
                else:
                    merged_config = example_config
                project_config = merged_config
                # Save the merged config
                try:
                    save_yaml_file(project_config_path, project_config, create_backup=True)
                    logger.info(
                        f"Initialized/merged config with example template: {example_config_path}"
                    )
                except Exception as e:
                    logger.warning(f"Failed to save merged config: {e}")
            elif not project_config:
                # No example found and no existing config, use empty
                project_config = {}

        user_config_path = Path.home() / ".tactus" / "config.yml"
        user_config = load_yaml_file(user_config_path) or {}

        # Try to find system config
        system_config_path = Path("/etc/tactus/config.yml")
        system_config = load_yaml_file(system_config_path) or {}

        # Determine which configs are writable
        writable_configs = {
            "system": False,  # System config is never writable from IDE
            "user": user_config_path.parent.exists() or True,  # Can create user config
            "project": True,  # Can always write to project config
        }

        return jsonify(
            {
                "config": effective_config,
                "project_config": project_config,
                "user_config": user_config,
                "system_config": system_config,
                "cascade": cascade_map,
                "source_details": source_details,
                "writable_configs": writable_configs,
                "config_paths": {
                    "system": str(system_config_path),
                    "user": str(user_config_path),
                    "project": str(project_config_path),
                },
                # Keep old fields for backward compatibility
                "project_config_path": str(project_config_path),
                "user_config_path": str(user_config_path),
            }
        )

    except Exception as e:
        logger.error(f"Error loading config: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@config_bp.route("", methods=["POST"])
def save_config():
    """
    Save configuration to specified target file.

    Request body:
        {
            "config": {...},
            "targetFile": "project" | "user",
            "createBackup": true
        }

    Returns:
        JSON response with success status and saved path
    """
    try:
        data = request.json

        if not data:
            return jsonify({"error": "Missing request body"}), 400

        config = data.get("config")
        target = data.get("targetFile", "project")
        create_backup = data.get("createBackup", True)

        if not config:
            return jsonify({"error": "Missing config"}), 400

        if not isinstance(config, dict):
            return jsonify({"error": "Config must be an object"}), 400

        # Determine target path
        if target == "project":
            config_path = Path.cwd() / ".tactus" / "config.yml"
        elif target == "user":
            config_path = Path.home() / ".tactus" / "config.yml"
        else:
            return jsonify({"error": f"Invalid target: {target}"}), 400

        # Save config
        save_yaml_file(config_path, config, create_backup)

        # Trigger a runtime reload by emitting an event or clearing caches
        # This ensures the new config is picked up without requiring a restart
        try:
            from tactus.ide.server import clear_runtime_caches

            clear_runtime_caches()
            logger.info("Cleared runtime caches after config save")
        except (ImportError, AttributeError):
            # If function doesn't exist yet, that's okay - just log it
            logger.debug("Runtime cache clearing not available")

        return jsonify({"success": True, "path": str(config_path)})

    except Exception as e:
        logger.error(f"Error saving config: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@config_bp.route("/save-by-source", methods=["POST"])
def save_config_by_source():
    """
    Save configuration changes to the appropriate file based on source tracking.

    This endpoint intelligently routes config changes to the correct file based on
    where each value is currently sourced from, or uses a fallback strategy.

    Request body:
        {
            "changes": {
                "aws.region": "us-west-2",
                "default_model": "gpt-4o"
            },
            "target_strategy": "source_aware" | "force_user" | "force_project"
        }

    Returns:
        JSON response with:
        - success: Boolean
        - saved_to: Dict mapping change paths to files they were saved to
        - errors: List of any errors (e.g., trying to override env var)
    """
    try:
        from tactus.core.config_manager import ConfigManager

        data = request.json

        if not data:
            return jsonify({"error": "Missing request body"}), 400

        changes = data.get("changes")
        strategy = data.get("target_strategy", "source_aware")

        if not changes:
            return jsonify({"error": "Missing changes"}), 400

        if not isinstance(changes, dict):
            return jsonify({"error": "Changes must be an object"}), 400

        # Load current config with sources
        config_manager = ConfigManager()
        dummy_path = Path.cwd() / "dummy.tac"
        effective_config, source_map = config_manager.load_cascade_with_sources(dummy_path)

        # Load current project and user configs
        project_config_path = Path.cwd() / ".tactus" / "config.yml"
        project_config = load_yaml_file(project_config_path) or {}

        user_config_path = Path.home() / ".tactus" / "config.yml"
        user_config = load_yaml_file(user_config_path) or {}

        saved_to = {}
        errors = []

        # Process each change
        for path, new_value in changes.items():
            # Determine target file based on strategy
            if strategy == "force_user":
                target_file = "user"
                target_config = user_config
            elif strategy == "force_project":
                target_file = "project"
                target_config = project_config
            else:  # source_aware
                # Check current source
                if path in source_map:
                    source_info = source_map[path]

                    # Check if sourced from environment variable
                    if source_info.is_env_override:
                        errors.append(
                            f"{path}: Cannot override environment variable "
                            f"{source_info.original_env_var} in config file"
                        )
                        continue

                    # Route to the source file
                    if source_info.source_type == "user":
                        target_file = "user"
                        target_config = user_config
                    elif source_info.source_type == "project":
                        target_file = "project"
                        target_config = project_config
                    else:
                        # For system or other sources, default to user config
                        target_file = "user"
                        target_config = user_config
                else:
                    # New value, default to user config
                    target_file = "user"
                    target_config = user_config

            # Update the target config dict
            _set_nested_value(target_config, path, new_value)
            saved_to[path] = target_file

        # Save modified configs
        if any(v == "user" for v in saved_to.values()):
            save_yaml_file(user_config_path, user_config, create_backup=True)

        if any(v == "project" for v in saved_to.values()):
            save_yaml_file(project_config_path, project_config, create_backup=True)

        return jsonify(
            {
                "success": len(errors) == 0,
                "saved_to": saved_to,
                "errors": errors,
            }
        )

    except Exception as e:
        logger.error(f"Error saving config by source: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


def _set_nested_value(config: Dict[str, Any], path: str, value: Any) -> None:
    """
    Set a nested value in a config dict using dot notation path.

    Args:
        config: Configuration dictionary to modify
        path: Dot-separated path (e.g., "aws.region")
        value: Value to set
    """
    keys = path.split(".")
    current = config

    # Navigate to the parent of the target key
    for key in keys[:-1]:
        if key not in current:
            current[key] = {}
        elif not isinstance(current[key], dict):
            # Path conflicts with existing non-dict value
            raise ValueError(f"Cannot set nested value: {key} is not a dict")
        current = current[key]

    # Set the final value
    current[keys[-1]] = value


@config_bp.route("/validate", methods=["POST"])
def validate_config():
    """
    Validate configuration structure without saving.

    Request body:
        {
            "config": {...}
        }

    Returns:
        JSON response with validation results
    """
    try:
        data = request.json

        if not data:
            return jsonify({"error": "Missing request body"}), 400

        config = data.get("config")

        if not config:
            return jsonify({"error": "Missing config"}), 400

        errors = []
        warnings = []

        # Basic validation
        if not isinstance(config, dict):
            errors.append("Config must be an object")
            return jsonify({"valid": False, "errors": errors, "warnings": warnings})

        # Validate known structure (optional - can be expanded)
        # Check for common mistakes
        if "default_provider" in config:
            if config["default_provider"] not in ["openai", "bedrock", "google"]:
                warnings.append(
                    f"Unknown provider: {config['default_provider']}. Expected openai, bedrock, or google."
                )

        if "ide" in config:
            ide_config = config["ide"]
            if not isinstance(ide_config, dict):
                errors.append("ide config must be an object")

        # Try to serialize to YAML (validation)
        try:
            yaml.safe_dump(config)
        except Exception as e:
            errors.append(f"Config cannot be serialized to YAML: {str(e)}")

        return jsonify(
            {
                "valid": len(errors) == 0,
                "errors": errors,
                "warnings": warnings,
            }
        )

    except Exception as e:
        logger.error(f"Error validating config: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


def register_config_routes(app):
    """
    Register config routes with Flask app.

    Args:
        app: Flask application instance
    """
    app.register_blueprint(config_bp)
    logger.info("Registered config API routes")
