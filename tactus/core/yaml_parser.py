"""
YAML Parser and Validator for Lua DSL Procedures.

Parses procedure YAML configurations and validates required structure.
"""

import yaml
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


class ProcedureConfigError(Exception):
    """Raised when procedure configuration is invalid."""

    pass


class ProcedureYAMLParser:
    """Parses and validates Lua DSL procedure YAML configurations."""

    @staticmethod
    def parse(yaml_content: str) -> Dict[str, Any]:
        """
        Parse YAML content into a validated procedure configuration.

        Args:
            yaml_content: YAML string to parse

        Returns:
            Validated configuration dictionary

        Raises:
            ProcedureConfigError: If YAML is invalid or missing required fields
        """
        try:
            config = yaml.safe_load(yaml_content)
        except yaml.YAMLError as e:
            raise ProcedureConfigError(f"Invalid YAML syntax: {e}")

        if not isinstance(config, dict):
            raise ProcedureConfigError("YAML root must be a dictionary")

        # Validate required top-level fields
        ProcedureYAMLParser._validate_required_fields(config)

        # Validate specific sections
        ProcedureYAMLParser._validate_params(config.get("params", {}))
        ProcedureYAMLParser._validate_outputs(config.get("outputs", {}))
        ProcedureYAMLParser._validate_default_model(config.get("default_model"))
        ProcedureYAMLParser._validate_default_provider(config.get("default_provider"))
        ProcedureYAMLParser._validate_agents(config.get("agents", {}), config)
        ProcedureYAMLParser._validate_procedure(config.get("procedure"))

        logger.info(f"Successfully parsed procedure: {config.get('name')}")
        return config

    @staticmethod
    def _validate_required_fields(config: Dict[str, Any]) -> None:
        """Validate that required top-level fields are present."""
        required = ["name", "version", "procedure"]
        missing = [field for field in required if field not in config]

        if missing:
            raise ProcedureConfigError(f"Missing required fields: {', '.join(missing)}")

        # Validate class field if present (for routing)
        if "class" in config:
            if config["class"] != "LuaDSL":
                logger.warning(
                    f"Procedure class '{config['class']}' may not be compatible "
                    "with Lua DSL runtime"
                )

    @staticmethod
    def _validate_params(params: Dict[str, Any]) -> None:
        """Validate parameter definitions."""
        if not isinstance(params, dict):
            raise ProcedureConfigError("'params' must be a dictionary")

        for param_name, param_def in params.items():
            if not isinstance(param_def, dict):
                raise ProcedureConfigError(
                    f"Parameter '{param_name}' definition must be a dictionary"
                )

            # Validate type field if present
            if "type" in param_def:
                valid_types = ["string", "number", "boolean", "array", "object"]
                if param_def["type"] not in valid_types:
                    raise ProcedureConfigError(
                        f"Parameter '{param_name}' has invalid type: {param_def['type']}. "
                        f"Must be one of: {', '.join(valid_types)}"
                    )

    @staticmethod
    def _validate_outputs(outputs: Dict[str, Any]) -> None:
        """Validate output definitions."""
        if not isinstance(outputs, dict):
            raise ProcedureConfigError("'outputs' must be a dictionary")

        for output_name, output_def in outputs.items():
            if not isinstance(output_def, dict):
                raise ProcedureConfigError(
                    f"Output '{output_name}' definition must be a dictionary"
                )

            # Validate type field if present
            if "type" in output_def:
                valid_types = ["string", "number", "boolean", "array", "object"]
                if output_def["type"] not in valid_types:
                    raise ProcedureConfigError(
                        f"Output '{output_name}' has invalid type: {output_def['type']}. "
                        f"Must be one of: {', '.join(valid_types)}"
                    )

    @staticmethod
    def _validate_default_model(default_model: Optional[str]) -> None:
        """Validate default_model field if present."""
        if default_model is not None:
            if not isinstance(default_model, str):
                raise ProcedureConfigError("'default_model' must be a string")
            if not default_model.strip():
                raise ProcedureConfigError("'default_model' cannot be empty")

    @staticmethod
    def _validate_default_provider(default_provider: Optional[str]) -> None:
        """Validate default_provider field if present."""
        if default_provider is not None:
            if not isinstance(default_provider, str):
                raise ProcedureConfigError("'default_provider' must be a string")
            if not default_provider.strip():
                raise ProcedureConfigError("'default_provider' cannot be empty")
            # Validate it's a known provider
            valid_providers = ["openai", "bedrock"]
            if default_provider not in valid_providers:
                raise ProcedureConfigError(
                    f"'default_provider' must be one of: {', '.join(valid_providers)}. "
                    f"Got: {default_provider}"
                )

    @staticmethod
    def _validate_agents(agents: Dict[str, Any], config: Dict[str, Any]) -> None:
        """Validate agent definitions."""
        if not isinstance(agents, dict):
            raise ProcedureConfigError("'agents' must be a dictionary")

        if not agents:
            raise ProcedureConfigError("At least one agent must be defined")

        for agent_name, agent_def in agents.items():
            if not isinstance(agent_def, dict):
                raise ProcedureConfigError(f"Agent '{agent_name}' definition must be a dictionary")

            # Validate required agent fields
            required_agent_fields = ["system_prompt", "initial_message"]
            missing = [field for field in required_agent_fields if field not in agent_def]

            if missing:
                raise ProcedureConfigError(
                    f"Agent '{agent_name}' missing required fields: {', '.join(missing)}"
                )

            # Validate model field if present
            if "model" in agent_def:
                model_value = agent_def["model"]

                # Model can be either a string or a dict with settings
                if isinstance(model_value, str):
                    if not model_value.strip():
                        raise ProcedureConfigError(f"Agent '{agent_name}' model cannot be empty")
                elif isinstance(model_value, dict):
                    # Model is a dict - must have 'name' key
                    if "name" not in model_value:
                        raise ProcedureConfigError(
                            f"Agent '{agent_name}' model dict must have a 'name' key"
                        )
                    if not isinstance(model_value["name"], str):
                        raise ProcedureConfigError(
                            f"Agent '{agent_name}' model name must be a string"
                        )
                    if not model_value["name"].strip():
                        raise ProcedureConfigError(
                            f"Agent '{agent_name}' model name cannot be empty"
                        )

                    # Validate model settings in the dict
                    valid_settings = {
                        "name",  # The model name itself
                        # Standard parameters (GPT-4 models)
                        "temperature",
                        "top_p",
                        "max_tokens",
                        "presence_penalty",
                        "frequency_penalty",
                        "logit_bias",
                        "stop_sequences",
                        "seed",
                        "parallel_tool_calls",
                        "timeout",
                        # OpenAI reasoning models (o1, GPT-5)
                        "openai_reasoning_effort",
                        # Extra fields
                        "extra_headers",
                        "extra_body",
                    }

                    for setting_key in model_value.keys():
                        if setting_key not in valid_settings:
                            raise ProcedureConfigError(
                                f"Agent '{agent_name}' has unknown model setting: '{setting_key}'. "
                                f"Valid keys: {', '.join(sorted(valid_settings))}"
                            )

                    # Validate specific field types
                    if "temperature" in model_value:
                        temp = model_value["temperature"]
                        if not isinstance(temp, (int, float)) or temp < 0 or temp > 2:
                            raise ProcedureConfigError(
                                f"Agent '{agent_name}' temperature must be a number between 0 and 2"
                            )

                    if "top_p" in model_value:
                        top_p = model_value["top_p"]
                        if not isinstance(top_p, (int, float)) or top_p < 0 or top_p > 1:
                            raise ProcedureConfigError(
                                f"Agent '{agent_name}' top_p must be a number between 0 and 1"
                            )

                    if "max_tokens" in model_value:
                        max_tok = model_value["max_tokens"]
                        if not isinstance(max_tok, int) or max_tok < 1:
                            raise ProcedureConfigError(
                                f"Agent '{agent_name}' max_tokens must be a positive integer"
                            )

                    if "openai_reasoning_effort" in model_value:
                        effort = model_value["openai_reasoning_effort"]
                        valid_efforts = ["low", "medium", "high"]
                        if effort not in valid_efforts:
                            raise ProcedureConfigError(
                                f"Agent '{agent_name}' openai_reasoning_effort must be one of: {', '.join(valid_efforts)}. "
                                f"Got: {effort}"
                            )
                else:
                    raise ProcedureConfigError(
                        f"Agent '{agent_name}' model must be a string or dict with 'name' key"
                    )

            # Validate provider field - required unless default_provider is set
            has_default_provider = "default_provider" in config
            if "provider" not in agent_def and not has_default_provider:
                raise ProcedureConfigError(
                    f"Agent '{agent_name}' must specify 'provider' (or set 'default_provider' at procedure level)"
                )

            if "provider" in agent_def:
                if not isinstance(agent_def["provider"], str):
                    raise ProcedureConfigError(f"Agent '{agent_name}' provider must be a string")
                if not agent_def["provider"].strip():
                    raise ProcedureConfigError(f"Agent '{agent_name}' provider cannot be empty")
                # Validate it's a known provider
                valid_providers = ["openai", "bedrock"]
                if agent_def["provider"] not in valid_providers:
                    raise ProcedureConfigError(
                        f"Agent '{agent_name}' provider must be one of: {', '.join(valid_providers)}. "
                        f"Got: {agent_def['provider']}"
                    )

            # Validate tools field if present
            if "tools" in agent_def:
                if not isinstance(agent_def["tools"], list):
                    raise ProcedureConfigError(f"Agent '{agent_name}' tools must be a list")

    @staticmethod
    def _validate_procedure(procedure: Optional[str]) -> None:
        """Validate procedure Lua code."""
        if not procedure:
            raise ProcedureConfigError("'procedure' field is required")

        if not isinstance(procedure, str):
            raise ProcedureConfigError("'procedure' must be a string")

        if not procedure.strip():
            raise ProcedureConfigError("'procedure' cannot be empty")

        # Basic Lua syntax check (just verify it's not obviously broken)
        # The actual Lua runtime will do full validation
        if procedure.count("(") != procedure.count(")"):
            logger.warning("Procedure has unmatched parentheses - may have syntax errors")

    @staticmethod
    def extract_agent_names(config: Dict[str, Any]) -> List[str]:
        """Extract list of agent names from configuration."""
        return list(config.get("agents", {}).keys())

    @staticmethod
    def get_agent_config(config: Dict[str, Any], agent_name: str) -> Optional[Dict[str, Any]]:
        """Get configuration for a specific agent."""
        return config.get("agents", {}).get(agent_name)
