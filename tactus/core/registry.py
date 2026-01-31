"""
Registry system for Lua DSL declarations.

This module provides Pydantic models for collecting and validating
procedure declarations from .tac files.
"""

import logging
from typing import Any

from pydantic import BaseModel, Field, ValidationError, ConfigDict

logger = logging.getLogger(__name__)


class OutputFieldDeclaration(BaseModel):
    """Output field declaration from DSL."""

    name: str
    field_type: str = Field(alias="type")  # string, number, boolean, array, object
    required: bool = False
    description: str | None = None

    model_config = ConfigDict(populate_by_name=True)


class MessageHistoryConfiguration(BaseModel):
    """Message history configuration for agents.

    Aligned with pydantic-ai's message_history concept.
    """

    source: str = "own"  # "own", "shared", or another agent's name
    filter: Any | None = None  # Lua function reference or filter name


class AgentOutputSchema(BaseModel):
    """Maps to Pydantic AI's output."""

    fields: dict[str, OutputFieldDeclaration] = Field(default_factory=dict)


class AgentDeclaration(BaseModel):
    """Agent declaration from DSL."""

    name: str
    provider: str | None = None
    model: str | dict[str, Any] = "gpt-4o"
    system_prompt: str | Any  # String with {markers} or Lua function
    initial_message: str | None = None
    tools: list[Any] = Field(default_factory=list)  # Tool/toolset references and expressions
    inline_tools: list[dict[str, Any]] = Field(default_factory=list)  # Inline tool definitions
    output: AgentOutputSchema | None = None  # Aligned with pydantic-ai
    message_history: MessageHistoryConfiguration | None = None
    max_turns: int = 50
    disable_streaming: bool = (
        False  # Disable streaming for models that don't support tools in streaming mode
    )
    temperature: float | None = None
    max_tokens: int | None = None
    model_type: str | None = None  # e.g., "chat", "responses" for reasoning models

    model_config = ConfigDict(extra="allow")


class HITLDeclaration(BaseModel):
    """Human-in-the-loop interaction point declaration."""

    name: str
    hitl_type: str = Field(alias="type")  # approval, input, review
    message: str
    timeout: int | None = None
    default: Any = None
    options: list[dict[str, Any]] | None = None

    model_config = ConfigDict(populate_by_name=True)


class ScenarioDeclaration(BaseModel):
    """BDD scenario declaration."""

    name: str
    given: dict[str, Any] = Field(default_factory=dict)
    when: str | None = None  # defaults to "procedure_completes"
    then_output: dict[str, Any] | None = None
    then_state: dict[str, Any] | None = None
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


class AgentMockConfig(BaseModel):
    """Mock configuration for an agent's behavior.

    Specifies what tool calls the agent should simulate when mocking is enabled.
    This allows agent-based tests to pass in CI without making real LLM calls.
    """

    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    # List of tool calls to simulate: [{"tool": "done", "args": {"reason": "..."}}, ...]
    message: str = ""  # The agent's final message response
    data: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional structured response payload (exposed as result.data in Lua)",
    )
    usage: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional token usage payload (exposed as result.usage in Lua)",
    )
    temporal: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Optional temporal mock turns (1-indexed by agent turn).",
    )


class ProcedureRegistry(BaseModel):
    """Collects all declarations from a .tac file."""

    model_config = {"arbitrary_types_allowed": True}

    # Metadata
    description: str | None = None

    # Declarations
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    state_schema: dict[str, Any] = Field(default_factory=dict)
    agents: dict[str, AgentDeclaration] = Field(default_factory=dict)
    models: dict[str, dict[str, Any]] = Field(default_factory=dict)  # ML models
    toolsets: dict[str, dict[str, Any]] = Field(default_factory=dict)
    lua_tools: dict[str, dict[str, Any]] = Field(default_factory=dict)  # Lua function tools
    hitl_points: dict[str, HITLDeclaration] = Field(default_factory=dict)
    specifications: list[SpecificationDeclaration] = Field(default_factory=list)
    dependencies: dict[str, DependencyDeclaration] = Field(default_factory=dict)
    mocks: dict[str, dict[str, Any]] = Field(default_factory=dict)  # Mock configurations
    agent_mocks: dict[str, AgentMockConfig] = Field(default_factory=dict)  # Agent mock configs

    # Message history configuration (aligned with pydantic-ai)
    message_history_config: dict[str, Any] = Field(default_factory=dict)

    # Gherkin BDD Testing
    gherkin_specifications: str | None = None  # Raw Gherkin text
    specs_from_references: list[str] = Field(default_factory=list)  # External spec file paths
    custom_steps: dict[str, Any] = Field(default_factory=dict)  # step_text -> lua_function
    evaluation_config: dict[str, Any] = Field(default_factory=dict)  # runs, parallel, etc.

    # Pydantic Evals Integration
    pydantic_evaluations: dict[str, Any] | None = None  # Pydantic Evals configuration

    # Prompts
    prompts: dict[str, str] = Field(default_factory=dict)
    return_prompt: str | None = None
    error_prompt: str | None = None
    status_prompt: str | None = None

    # Execution settings
    async_enabled: bool = False
    max_depth: int = 5
    max_turns: int = 50
    default_provider: str | None = None
    default_model: str | None = None

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
    location: tuple[int, int] | None = None
    declaration: str | None = None


class ValidationResult(BaseModel):
    """Result of validation."""

    valid: bool
    errors: list[ValidationMessage] = Field(default_factory=list)
    warnings: list[ValidationMessage] = Field(default_factory=list)
    registry: ProcedureRegistry | None = None


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

    def register_agent(
        self,
        name: str,
        config: dict,
        output_schema: dict | None = None,
    ) -> None:
        """Register an agent declaration."""
        agent_config = dict(config)
        agent_config["name"] = name

        # Add output_schema to config if provided
        if output_schema:
            # Convert output_schema dict to AgentOutputSchema
            output_field_declarations: dict[str, OutputFieldDeclaration] = {}
            for field_name, field_definition in output_schema.items():
                # Add the field name to the config (required by OutputFieldDeclaration)
                field_definition_with_name = dict(field_definition)
                field_definition_with_name["name"] = field_name
                output_field_declarations[field_name] = OutputFieldDeclaration(
                    **field_definition_with_name
                )
            agent_config["output"] = AgentOutputSchema(fields=output_field_declarations)

        # Apply defaults
        if "provider" not in agent_config and self.registry.default_provider:
            agent_config["provider"] = self.registry.default_provider
        if "model" not in agent_config and self.registry.default_model:
            agent_config["model"] = self.registry.default_model
        try:
            self.registry.agents[name] = AgentDeclaration(**agent_config)
        except ValidationError as exception:
            self._add_error(f"Invalid agent '{name}': {exception}")

    def register_model(self, name: str, config: dict) -> None:
        """Register a model declaration."""
        config["name"] = name
        self.registry.models[name] = config

    def register_hitl(self, name: str, config: dict) -> None:
        """Register a HITL interaction point."""
        config["name"] = name
        try:
            self.registry.hitl_points[name] = HITLDeclaration(**config)
        except ValidationError as exception:
            self._add_error(f"Invalid HITL point '{name}': {exception}")

    def register_dependency(self, name: str, config: dict) -> None:
        """Register a dependency declaration."""
        # The config dict contains the type and all other configuration
        dependency_declaration = {
            "name": name,
            "type": config.get("type"),
            "config": config,  # Store the entire config dict
        }
        try:
            self.registry.dependencies[name] = DependencyDeclaration(**dependency_declaration)
        except ValidationError as exception:
            self._add_error(f"Invalid dependency '{name}': {exception}")

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
            config: Dict with description, input, output schemas, and source info
            lua_handler: Lupa function reference (or placeholder for external sources)
        """
        tool_definition = {
            "description": config.get("description", ""),
            "input": config.get("input", {}),  # Changed from parameters
            "output": config.get("output", {}),  # New: output schema
            "handler": lua_handler,
        }

        # If this tool references an external source, store that info
        if "source" in config:
            tool_definition["source"] = config["source"]

        self.registry.lua_tools[name] = tool_definition

    def register_mock(self, tool_name: str, config: dict) -> None:
        """Register a mock configuration for a tool.

        Args:
            tool_name: Name of the tool to mock
            config: Mock configuration (output, temporal, conditional_mocks, error)
        """
        self.registry.mocks[tool_name] = config

    def register_agent_mock(self, agent_name: str, config: dict) -> None:
        """Register a mock configuration for an agent.

        Args:
            agent_name: Name of the agent to mock
            config: Mock configuration with tool_calls and message
        """
        try:
            self.registry.agent_mocks[agent_name] = AgentMockConfig(**config)
        except Exception as exception:
            self._add_error(f"Invalid agent mock config for '{agent_name}': {exception}")

    def register_specification(self, name: str, scenarios: list) -> None:
        """Register a BDD specification."""
        try:
            spec = SpecificationDeclaration(
                name=name, scenarios=[ScenarioDeclaration(**s) for s in scenarios]
            )
            self.registry.specifications.append(spec)
        except ValidationError as exception:
            self._add_error(f"Invalid specification '{name}': {exception}")

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

        # If this is the main entry point, also populate the top-level schemas so
        # runtime output validation and tooling use a single canonical `output`.
        if name == "main":
            self.registry.input_schema = input_schema
            self.registry.output_schema = output_schema
            self.registry.state_schema = state_schema

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

    def register_specs_from(self, file_path: str) -> None:
        """Register a reference to external specifications.

        Stores the path for lazy loading. Actual spec content
        is loaded during test execution, not parse time.

        Args:
            file_path: Path to .spec.tac file or module name
        """
        self.registry.specs_from_references.append(file_path)

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
        validation_errors: list[ValidationMessage] = []
        validation_warnings: list[ValidationMessage] = []

        # Script mode: merge top-level schemas into main procedure
        if self.registry.script_mode and "main" in self.registry.named_procedures:
            main_procedure_entry = self.registry.named_procedures["main"]
            # Merge top-level input schema if main doesn't have one
            if not main_procedure_entry["input_schema"] and self.registry.top_level_input_schema:
                main_procedure_entry["input_schema"] = self.registry.top_level_input_schema
            # Merge top-level output schema if main doesn't have one
            if not main_procedure_entry["output_schema"] and self.registry.top_level_output_schema:
                main_procedure_entry["output_schema"] = self.registry.top_level_output_schema

        # Check for multiple unnamed Procedures (all would register as "main")
        # Count how many times a procedure was registered as "main"
        main_procedure_declaration_count = sum(
            1 for name in self.registry.named_procedures.keys() if name == "main"
        )
        if main_procedure_declaration_count > 1:
            validation_errors.append(
                ValidationMessage(
                    level="error",
                    message="Multiple unnamed Procedures found. Only one unnamed Procedure is allowed as the main entry point. Use named Procedures (e.g., helper = Procedure {...}) for additional procedures.",
                )
            )

        # Note: With immediate agent creation, Procedures are optional.
        # Top-level code can execute directly without being wrapped in a Procedure.

        # Agent validation
        for agent_declaration in self.registry.agents.values():
            # Check if agent has provider or if there's a default
            if not agent_declaration.provider and not self.registry.default_provider:
                validation_errors.append(
                    ValidationMessage(
                        level="error",
                        message=f"Agent '{agent_declaration.name}' missing provider",
                        declaration=agent_declaration.name,
                    )
                )

        # Warnings for missing specifications
        has_specifications = (
            self.registry.specifications
            or self.registry.gherkin_specifications
            or self.registry.specs_from_references
        )
        if not has_specifications:
            validation_warnings.append(
                ValidationMessage(
                    level="warning",
                    message='No specifications defined - consider adding BDD tests using Specification([[...]]) or Specification { from = "path" }',
                )
            )

        # Add any errors from registration
        validation_errors.extend(
            [message for message in self.validation_messages if message.level == "error"]
        )
        validation_warnings.extend(
            [message for message in self.validation_messages if message.level == "warning"]
        )

        return ValidationResult(
            valid=len(validation_errors) == 0,
            errors=validation_errors,
            warnings=validation_warnings,
            registry=self.registry if len(validation_errors) == 0 else None,
        )
