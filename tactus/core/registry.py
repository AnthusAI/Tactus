"""
Registry system for Lua DSL declarations.

This module provides Pydantic models for collecting and validating
procedure declarations from .tac files.
"""

from enum import Enum
from typing import Any, Optional, Union

from pydantic import BaseModel, Field, ValidationError


class ParameterType(str, Enum):
    """Parameter type enumeration."""

    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"


class ParameterDeclaration(BaseModel):
    """Parameter declaration from DSL."""

    name: str
    parameter_type: ParameterType = Field(alias="type")
    required: bool = False
    default: Any = None
    description: Optional[str] = None
    enum: Optional[list[str]] = None

    class Config:
        populate_by_name = True


class OutputFieldDeclaration(BaseModel):
    """Output field declaration from DSL."""

    name: str
    field_type: ParameterType = Field(alias="type")
    required: bool = False
    description: Optional[str] = None

    class Config:
        populate_by_name = True


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
    tools: list[str] = Field(default_factory=list)
    output: Optional[AgentOutputSchema] = None  # Legacy field
    output_type: Optional[AgentOutputSchema] = None  # Aligned with pydantic-ai
    message_history: Optional[MessageHistoryConfiguration] = None
    max_turns: int = 50


class HITLDeclaration(BaseModel):
    """Human-in-the-loop interaction point declaration."""

    name: str
    hitl_type: str = Field(alias="type")  # approval, input, review
    message: str
    timeout: Optional[int] = None
    default: Any = None
    options: Optional[list[dict[str, Any]]] = None

    class Config:
        populate_by_name = True


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


class ProcedureRegistry(BaseModel):
    """Collects all declarations from a .tac file."""

    model_config = {"arbitrary_types_allowed": True}

    # Metadata
    description: Optional[str] = None

    # Declarations
    parameters: dict[str, ParameterDeclaration] = Field(default_factory=dict)
    outputs: dict[str, OutputFieldDeclaration] = Field(default_factory=dict)
    agents: dict[str, AgentDeclaration] = Field(default_factory=dict)
    hitl_points: dict[str, HITLDeclaration] = Field(default_factory=dict)
    stages: list[str] = Field(default_factory=list)
    specifications: list[SpecificationDeclaration] = Field(default_factory=list)

    # Message history configuration (aligned with pydantic-ai)
    message_history_config: dict[str, Any] = Field(default_factory=dict)

    # Gherkin BDD Testing
    gherkin_specifications: Optional[str] = None  # Raw Gherkin text
    custom_steps: dict[str, Any] = Field(default_factory=dict)  # step_text -> lua_function
    evaluation_config: dict[str, Any] = Field(default_factory=dict)  # runs, parallel, etc.

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

    # The procedure function (lupa reference, not executed during registration)
    procedure_function: Any = Field(default=None, exclude=True)

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

    def register_parameter(self, name: str, config: dict) -> None:
        """Register a parameter declaration."""
        config["name"] = name
        try:
            self.registry.parameters[name] = ParameterDeclaration(**config)
        except ValidationError as e:
            self._add_error(f"Invalid parameter '{name}': {e}")

    def register_output(self, name: str, config: dict) -> None:
        """Register an output field declaration."""
        config["name"] = name
        try:
            self.registry.outputs[name] = OutputFieldDeclaration(**config)
        except ValidationError as e:
            self._add_error(f"Invalid output '{name}': {e}")

    def register_agent(self, name: str, config: dict, output_schema: Optional[dict] = None) -> None:
        """Register an agent declaration."""
        config["name"] = name

        # Add output_schema to config if provided
        if output_schema:
            # Convert output_schema dict to AgentOutputSchema
            fields = {}
            for field_name, field_config in output_schema.items():
                fields[field_name] = OutputFieldDeclaration(**field_config)
            config["output_type"] = AgentOutputSchema(fields=fields)

        # Apply defaults
        if "provider" not in config and self.registry.default_provider:
            config["provider"] = self.registry.default_provider
        if "model" not in config and self.registry.default_model:
            config["model"] = self.registry.default_model
        try:
            self.registry.agents[name] = AgentDeclaration(**config)
        except ValidationError as e:
            self._add_error(f"Invalid agent '{name}': {e}")

    def register_hitl(self, name: str, config: dict) -> None:
        """Register a HITL interaction point."""
        config["name"] = name
        try:
            self.registry.hitl_points[name] = HITLDeclaration(**config)
        except ValidationError as e:
            self._add_error(f"Invalid HITL point '{name}': {e}")

    def register_prompt(self, name: str, content: str) -> None:
        """Register a prompt template."""
        self.registry.prompts[name] = content

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

    def set_procedure(self, lua_function) -> None:
        """Store Lua function reference for later execution."""
        self.registry.procedure_function = lua_function

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

        # Required fields
        if not self.registry.procedure_function:
            errors.append(ValidationMessage(level="error", message="procedure is required"))

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
