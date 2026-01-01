"""
Registry system for Lua DSL declarations.

This module provides Pydantic models for collecting and validating
procedure declarations from .tac files.
"""

import logging
from typing import Any, Optional, Union

from pydantic import BaseModel, Field, ValidationError, ConfigDict

logger = logging.getLogger(__name__)


class OutputFieldDeclaration(BaseModel):
    """Output field declaration from DSL."""

    name: str
    field_type: str = Field(alias="type")  # string, number, boolean, array, object
    required: bool = False
    description: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True)


class MessageHistoryConfiguration(BaseModel):
    """Message history configuration for agents.

    Aligned with pydantic-ai's message_history concept.
    """

    source: str = "own"  # "own", "shared", or another agent's name
    filter: Optional[Any] = None  # Lua function reference or filter name


class AgentOutputSchema(BaseModel):
    """Maps to Pydantic AI's output_type."""

    fields: dict[str, OutputFieldDeclaration] = Field(default_factory=dict)


class AgentDeclaration(BaseModel):
    """Agent declaration from DSL."""

    name: str
    provider: Optional[str] = None
    model: Union[str, dict[str, Any]] = "gpt-4o"
    system_prompt: Union[str, Any]  # String with {markers} or Lua function
    initial_message: Optional[str] = None
    tools: list[Union[str, dict[str, Any]]] = Field(
        default_factory=list
    )  # Supports toolset expressions
    inline_tool_defs: list[dict[str, Any]] = Field(
        default_factory=list
    )  # Inline tool definitions with Lua handlers
    output: Optional[AgentOutputSchema] = None  # Legacy field
    output_type: Optional[AgentOutputSchema] = None  # Aligned with pydantic-ai
    message_history: Optional[MessageHistoryConfiguration] = None
    max_turns: int = 50
    disable_streaming: bool = (
        False  # Disable streaming for models that don't support tools in streaming mode
    )

    model_config = ConfigDict(extra="allow")


class HITLDeclaration(BaseModel):
    """Human-in-the-loop interaction point declaration."""

    name: str
    hitl_type: str = Field(alias="type")  # approval, input, review
    message: str
    timeout: Optional[int] = None
    default: Any = None
    options: Optional[list[dict[str, Any]]] = None

    model_config = ConfigDict(populate_by_name=True)


class ScenarioDeclaration(BaseModel):
    """BDD scenario declaration."""

    name: str
    given: dict[str, Any] = Field(default_factory=dict)
    when: Optional[str] = None  # defaults to "procedure_completes"
    then_output: Optional[dict[str, Any]] = None
    then_state: Optional[dict[str, Any]] = None
    mocks: dict[str, Any] = Field(default_factory=dict)  # tool_name -> response


class SpecificationDeclaration(BaseModel):
    """BDD specification declaration."""

    name: str
    scenarios: list[ScenarioDeclaration] = Field(default_factory=list)


class DependencyDeclaration(BaseModel):
    """Dependency declaration from DSL."""

    name: str
    dependency_type: str = Field(alias="type")  # http_client, postgres, redis
    config: dict[str, Any] = Field(default_factory=dict)  # Configuration dict

    model_config = ConfigDict(populate_by_name=True)


class ProcedureRegistry(BaseModel):
    """Collects all declarations from a .tac file."""

    model_config = {"arbitrary_types_allowed": True}

    # Metadata
    description: Optional[str] = None

    # Declarations
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    state_schema: dict[str, Any] = Field(default_factory=dict)
    agents: dict[str, AgentDeclaration] = Field(default_factory=dict)
    models: dict[str, dict[str, Any]] = Field(default_factory=dict)  # ML models
    toolsets: dict[str, dict[str, Any]] = Field(default_factory=dict)
    lua_tools: dict[str, dict[str, Any]] = Field(default_factory=dict)  # Lua function tools
    hitl_points: dict[str, HITLDeclaration] = Field(default_factory=dict)
    stages: list[str] = Field(default_factory=list)
    specifications: list[SpecificationDeclaration] = Field(default_factory=list)
    dependencies: dict[str, DependencyDeclaration] = Field(default_factory=dict)

    # Message history configuration (aligned with pydantic-ai)
    message_history_config: dict[str, Any] = Field(default_factory=dict)

    # Gherkin BDD Testing
    gherkin_specifications: Optional[str] = None  # Raw Gherkin text
    custom_steps: dict[str, Any] = Field(default_factory=dict)  # step_text -> lua_function
    evaluation_config: dict[str, Any] = Field(default_factory=dict)  # runs, parallel, etc.

    # Pydantic Evals Integration
    pydantic_evaluations: Optional[dict[str, Any]] = None  # Pydantic Evals configuration

    # Prompts
    prompts: dict[str, str] = Field(default_factory=dict)
    return_prompt: Optional[str] = None
    error_prompt: Optional[str] = None
    status_prompt: Optional[str] = None

    # Execution settings
    async_enabled: bool = False
    max_depth: int = 5
    max_turns: int = 50
    default_provider: Optional[str] = None
    default_model: Optional[str] = None

    # Named procedures (for in-file sub-procedures)
    named_procedures: dict[str, dict[str, Any]] = Field(default_factory=dict)
    # Structure: {"proc_name": {"function": <lua_ref>, "input_schema": {...}, ...}}

    # Script mode support (top-level input/output without explicit main procedure)
    script_mode: bool = False
    top_level_input_schema: dict[str, Any] = Field(default_factory=dict)
    top_level_output_schema: dict[str, Any] = Field(default_factory=dict)

    # Source locations for error messages (declaration_name -> (line, col))
    source_locations: dict[str, tuple[int, int]] = Field(default_factory=dict)


class ValidationMessage(BaseModel):
    """Validation error or warning message."""

    level: str  # "error" or "warning"
    message: str
    location: Optional[tuple[int, int]] = None
    declaration: Optional[str] = None


class ValidationResult(BaseModel):
    """Result of validation."""

    valid: bool
    errors: list[ValidationMessage] = Field(default_factory=list)
    warnings: list[ValidationMessage] = Field(default_factory=list)
    registry: Optional[ProcedureRegistry] = None


class RegistryBuilder:
    """Builds ProcedureRegistry from DSL function calls."""

    def __init__(self):
        self.registry = ProcedureRegistry()
        self.validation_messages: list[ValidationMessage] = []

    def register_input_schema(self, schema: dict) -> None:
        """Register input schema declaration."""
        self.registry.input_schema = schema

    def register_output_schema(self, schema: dict) -> None:
        """Register output schema declaration."""
        self.registry.output_schema = schema

    def register_state_schema(self, schema: dict) -> None:
        """Register state schema declaration."""
        self.registry.state_schema = schema

    def register_agent(self, name: str, config: dict, output_schema: Optional[dict] = None) -> None:
        """Register an agent declaration."""
        config["name"] = name

        # Add output_schema to config if provided
        if output_schema:
            # Convert output_schema dict to AgentOutputSchema
            fields = {}
            for field_name, field_config in output_schema.items():
                # Add the field name to the config (required by OutputFieldDeclaration)
                field_config_with_name = dict(field_config)
                field_config_with_name["name"] = field_name
                fields[field_name] = OutputFieldDeclaration(**field_config_with_name)
            config["output_type"] = AgentOutputSchema(fields=fields)

        # Handle toolsets -> tools rename (backward compatibility)
        # The Lua DSL uses "toolsets" for toolset references and "tools" for inline tool definitions
        # AgentDeclaration expects "tools" for toolset references
        if "toolsets" in config:
            if "tools" in config:
                # Both exist: tools = inline defs, toolsets = references
                # Keep inline defs in a temp field, use toolsets as tools
                config["inline_tool_defs"] = config.pop("tools")
                config["tools"] = config.pop("toolsets")
            else:
                # Only toolsets exists: rename to tools
                config["tools"] = config.pop("toolsets")

        # Apply defaults
        if "provider" not in config and self.registry.default_provider:
            config["provider"] = self.registry.default_provider
        if "model" not in config and self.registry.default_model:
            config["model"] = self.registry.default_model
        try:
            self.registry.agents[name] = AgentDeclaration(**config)
        except ValidationError as e:
            self._add_error(f"Invalid agent '{name}': {e}")

    def register_model(self, name: str, config: dict) -> None:
        """Register a model declaration."""
        config["name"] = name
        self.registry.models[name] = config

    def register_hitl(self, name: str, config: dict) -> None:
        """Register a HITL interaction point."""
        config["name"] = name
        try:
            self.registry.hitl_points[name] = HITLDeclaration(**config)
        except ValidationError as e:
            self._add_error(f"Invalid HITL point '{name}': {e}")

    def register_dependency(self, name: str, config: dict) -> None:
        """Register a dependency declaration."""
        # The config dict contains the type and all other configuration
        dependency_config = {
            "name": name,
            "type": config.get("type"),
            "config": config,  # Store the entire config dict
        }
        try:
            self.registry.dependencies[name] = DependencyDeclaration(**dependency_config)
        except ValidationError as e:
            self._add_error(f"Invalid dependency '{name}': {e}")

    def register_prompt(self, name: str, content: str) -> None:
        """Register a prompt template."""
        self.registry.prompts[name] = content

    def register_toolset(self, name: str, config: dict) -> None:
        """Register a toolset definition from DSL."""
        self.registry.toolsets[name] = config

    def register_tool(self, name: str, config: dict, lua_handler: Any) -> None:
        """Register an individual Lua tool declaration.

        Args:
            name: Tool name
            config: Dict with description, parameters
            lua_handler: Lupa function reference
        """
        self.registry.lua_tools[name] = {
            "description": config.get("description", ""),
            "parameters": config.get("parameters", {}),
            "handler": lua_handler,
        }

    def set_stages(self, stage_names: list[str]) -> None:
        """Set stage names."""
        self.registry.stages = stage_names

    def register_specification(self, name: str, scenarios: list) -> None:
        """Register a BDD specification."""
        try:
            spec = SpecificationDeclaration(
                name=name, scenarios=[ScenarioDeclaration(**s) for s in scenarios]
            )
            self.registry.specifications.append(spec)
        except ValidationError as e:
            self._add_error(f"Invalid specification '{name}': {e}")

    def register_named_procedure(
        self,
        name: str,
        lua_function: Any,
        input_schema: dict[str, Any],
        output_schema: dict[str, Any],
        state_schema: dict[str, Any],
    ) -> None:
        """
        Register a named procedure for in-file calling.

        Args:
            name: Procedure name
            lua_function: Lua function reference
            input_schema: Input validation schema
            output_schema: Output validation schema
            state_schema: State initialization schema
        """
        self.registry.named_procedures[name] = {
            "function": lua_function,
            "input_schema": input_schema,
            "output_schema": output_schema,
            "state_schema": state_schema,
        }

    def register_top_level_input(self, schema: dict) -> None:
        """Register top-level input schema for script mode."""
        self.registry.top_level_input_schema = schema
        self.registry.script_mode = True

    def register_top_level_output(self, schema: dict) -> None:
        """Register top-level output schema for script mode."""
        self.registry.top_level_output_schema = schema
        self.registry.script_mode = True

    def set_default_provider(self, provider: str) -> None:
        """Set default provider for agents."""
        self.registry.default_provider = provider

    def set_default_model(self, model: str) -> None:
        """Set default model for agents."""
        self.registry.default_model = model

    def set_return_prompt(self, prompt: str) -> None:
        """Set return prompt."""
        self.registry.return_prompt = prompt

    def set_error_prompt(self, prompt: str) -> None:
        """Set error prompt."""
        self.registry.error_prompt = prompt

    def set_status_prompt(self, prompt: str) -> None:
        """Set status prompt."""
        self.registry.status_prompt = prompt

    def set_async(self, enabled: bool) -> None:
        """Set async execution flag."""
        self.registry.async_enabled = enabled

    def set_max_depth(self, depth: int) -> None:
        """Set maximum recursion depth."""
        self.registry.max_depth = depth

    def set_max_turns(self, turns: int) -> None:
        """Set maximum turns."""
        self.registry.max_turns = turns

    def register_specifications(self, gherkin_text: str) -> None:
        """Register Gherkin BDD specifications."""
        self.registry.gherkin_specifications = gherkin_text

    def register_custom_step(self, step_text: str, lua_function: Any) -> None:
        """Register a custom step definition."""
        self.registry.custom_steps[step_text] = lua_function

    def set_evaluation_config(self, config: dict) -> None:
        """Set evaluation configuration."""
        self.registry.evaluation_config = config

    def set_message_history_config(self, config: dict) -> None:
        """Set procedure-level message history configuration."""
        self.registry.message_history_config = config

    def register_evaluations(self, config: dict) -> None:
        """Register Pydantic Evals evaluation configuration."""
        self.registry.pydantic_evaluations = config

    def _add_error(self, message: str) -> None:
        """Add an error message."""
        self.validation_messages.append(ValidationMessage(level="error", message=message))

    def _add_warning(self, message: str) -> None:
        """Add a warning message."""
        self.validation_messages.append(ValidationMessage(level="warning", message=message))

    def validate(self) -> ValidationResult:
        """Run all validations after declarations collected."""
        errors = []
        warnings = []

        # Required field - named 'main' procedure
        if "main" not in self.registry.named_procedures:
            errors.append(
                ValidationMessage(
                    level="error",
                    message="named 'main' procedure is required",
                )
            )

        # Agent validation
        for agent in self.registry.agents.values():
            if not agent.provider:
                errors.append(
                    ValidationMessage(
                        level="error",
                        message=f"Agent '{agent.name}' missing provider",
                        declaration=agent.name,
                    )
                )

        # Warnings for missing specifications
        if not self.registry.specifications and not self.registry.gherkin_specifications:
            warnings.append(
                ValidationMessage(
                    level="warning",
                    message="No specifications defined - consider adding BDD tests using specifications([[...]])",
                )
            )

        # Add any errors from registration
        errors.extend([m for m in self.validation_messages if m.level == "error"])
        warnings.extend([m for m in self.validation_messages if m.level == "warning"])

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            registry=self.registry if len(errors) == 0 else None,
        )
