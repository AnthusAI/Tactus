# Coding Brief: Transform Tactus to Pure Lua DSL

## Executive Summary

Transform Tactus from a YAML+Lua hybrid to a **pure Lua DSL** (`.tac` files). The same source file works for ANTLR-based validation (IDE/CLI) and lupa execution (runtime). This is a **clean break** - all YAML parsing code will be deleted, all examples converted, and all tests updated.

## Core Architectural Insight

DSL declarations are **self-registering function calls** that are valid Lua syntax:

```lua
name "hello_world"
version "1.0.0"

parameter "topic" { type = "string", required = true }

agent "worker" {
    provider = "openai",
    model = "gpt-4o",
    system_prompt = [[Research: {params.topic}]],
    tools = {"search", "done"},
    output = {
        findings = { type = "string", required = true }
    }
}

procedure(function()
    repeat
        Worker.turn()
    until Tool.called("done")
    return { result = Tool.last_result("done") }
end)
```

**Why this works:**
- Lua allows `func "string" { table }` as sugar for `func("string", { table })`
- DSL functions register declarations in a registry
- Procedure function is stored (not executed) during declaration phase
- Runtime injects primitives, then calls the stored procedure function
- ANTLR validates syntax without execution

---

## File Structure

**Extension:** `.tac`

This gets free Lua syntax highlighting while being distinctive.

---

## 1. Registry Design

### Pydantic Models for Declarations

```python
from pydantic import BaseModel, Field
from typing import Any, Callable, Optional, Union
from enum import Enum


class ParameterType(str, Enum):
    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"


class ParameterDeclaration(BaseModel):
    name: str
    parameter_type: ParameterType = Field(alias="type")
    required: bool = False
    default: Any = None
    description: Optional[str] = None
    enum: Optional[list[str]] = None


class OutputFieldDeclaration(BaseModel):
    name: str
    field_type: ParameterType = Field(alias="type")
    required: bool = False
    description: Optional[str] = None


class SessionConfiguration(BaseModel):
    source: str = "own"  # "own", "shared", or another agent's name
    filter: Optional[Any] = None  # Lua function reference or filter name


class AgentOutputSchema(BaseModel):
    """Maps to Pydantic AI's output_type."""
    fields: dict[str, OutputFieldDeclaration] = Field(default_factory=dict)


class AgentDeclaration(BaseModel):
    name: str
    provider: str
    model: Union[str, dict[str, Any]] = "gpt-4o"
    system_prompt: Union[str, Any]  # String with {markers} or Lua function
    initial_message: Optional[str] = None
    tools: list[str] = Field(default_factory=list)
    output: Optional[AgentOutputSchema] = None
    session: Optional[SessionConfiguration] = None
    max_turns: int = 50


class HITLDeclaration(BaseModel):
    name: str
    hitl_type: str = Field(alias="type")  # approval, input, review
    message: str
    timeout: Optional[int] = None
    default: Any = None
    options: Optional[list[dict[str, Any]]] = None


class ScenarioDeclaration(BaseModel):
    name: str
    given: dict[str, Any] = Field(default_factory=dict)
    when: Optional[str] = None  # defaults to "procedure_completes"
    then_output: Optional[dict[str, Any]] = None
    then_state: Optional[dict[str, Any]] = None
    mocks: dict[str, Any] = Field(default_factory=dict)  # tool_name -> response


class SpecificationDeclaration(BaseModel):
    name: str
    scenarios: list[ScenarioDeclaration] = Field(default_factory=list)


class ProcedureRegistry(BaseModel):
    """Collects all declarations from a .tac file."""
    
    model_config = {"arbitrary_types_allowed": True}
    
    # Metadata
    procedure_name: Optional[str] = None
    version: Optional[str] = None
    description: Optional[str] = None
    
    # Declarations
    parameters: dict[str, ParameterDeclaration] = Field(default_factory=dict)
    outputs: dict[str, OutputFieldDeclaration] = Field(default_factory=dict)
    agents: dict[str, AgentDeclaration] = Field(default_factory=dict)
    hitl_points: dict[str, HITLDeclaration] = Field(default_factory=dict)
    stages: list[str] = Field(default_factory=list)
    specifications: list[SpecificationDeclaration] = Field(default_factory=list)
    
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
    level: str  # "error" or "warning"
    message: str
    location: Optional[tuple[int, int]] = None
    declaration: Optional[str] = None


class ValidationResult(BaseModel):
    valid: bool
    errors: list[ValidationMessage] = Field(default_factory=list)
    warnings: list[ValidationMessage] = Field(default_factory=list)
    registry: Optional[ProcedureRegistry] = None
```

### RegistryBuilder

```python
class RegistryBuilder:
    """Builds ProcedureRegistry from DSL function calls."""
    
    def __init__(self):
        self.registry = ProcedureRegistry()
        self.validation_messages: list[ValidationMessage] = []
    
    def set_name(self, name: str) -> None:
        self.registry.procedure_name = name
    
    def set_version(self, version: str) -> None:
        self.registry.version = version
    
    def register_parameter(self, name: str, config: dict) -> None:
        config["name"] = name
        try:
            self.registry.parameters[name] = ParameterDeclaration(**config)
        except ValidationError as e:
            self._add_error(f"Invalid parameter '{name}': {e}")
    
    def register_output(self, name: str, config: dict) -> None:
        config["name"] = name
        self.registry.outputs[name] = OutputFieldDeclaration(**config)
    
    def register_agent(self, name: str, config: dict) -> None:
        config["name"] = name
        # Apply defaults
        if "provider" not in config and self.registry.default_provider:
            config["provider"] = self.registry.default_provider
        if "model" not in config and self.registry.default_model:
            config["model"] = self.registry.default_model
        self.registry.agents[name] = AgentDeclaration(**config)
    
    def register_specification(self, name: str, scenarios: list) -> None:
        spec = SpecificationDeclaration(name=name, scenarios=[
            ScenarioDeclaration(**s) for s in scenarios
        ])
        self.registry.specifications.append(spec)
    
    def set_procedure(self, lua_function) -> None:
        """Store Lua function reference for later execution."""
        self.registry.procedure_function = lua_function
    
    def validate(self) -> ValidationResult:
        """Run all validations after declarations collected."""
        errors = []
        warnings = []
        
        # Required fields
        if not self.registry.procedure_name:
            errors.append(ValidationMessage(level="error", message="name is required"))
        if not self.registry.procedure_function:
            errors.append(ValidationMessage(level="error", message="procedure is required"))
        
        # Agent validation
        for agent in self.registry.agents.values():
            if not agent.provider:
                errors.append(ValidationMessage(
                    level="error",
                    message=f"Agent '{agent.name}' missing provider",
                    declaration=agent.name
                ))
        
        # Warnings
        if not self.registry.specifications:
            warnings.append(ValidationMessage(
                level="warning",
                message="No specifications defined - consider adding tests"
            ))
        
        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            registry=self.registry if len(errors) == 0 else None
        )
```

---

## 2. DSL Function Stubs

Before executing a `.tac` file, inject these functions into lupa:

```python
def create_dsl_stubs(builder: RegistryBuilder) -> dict[str, Callable]:
    """Create DSL stub functions that populate the registry."""
    
    def lua_table_to_dict(lua_table) -> dict:
        """Convert lupa table to Python dict recursively."""
        # Implementation handles nested tables, arrays, etc.
        ...
    
    return {
        "name": lambda value: builder.set_name(value),
        "version": lambda value: builder.set_version(value),
        "description": lambda value: builder.set_description(value),
        
        "parameter": lambda param_name, config=None: 
            builder.register_parameter(param_name, lua_table_to_dict(config or {})),
        
        "output": lambda output_name, config=None:
            builder.register_output(output_name, lua_table_to_dict(config or {})),
        
        "agent": lambda agent_name, config:
            builder.register_agent(agent_name, lua_table_to_dict(config)),
        
        "procedure": lambda lua_function:
            builder.set_procedure(lua_function),
        
        "prompt": lambda prompt_name, content:
            builder.register_prompt(prompt_name, content),
        
        "hitl": lambda hitl_name, config:
            builder.register_hitl(hitl_name, lua_table_to_dict(config)),
        
        "stages": lambda *stage_names:
            builder.set_stages(list(stage_names)),
        
        "specification": lambda spec_name, scenarios:
            builder.register_specification(spec_name, lua_table_to_dict(scenarios)),
        
        "default_provider": lambda provider:
            builder.set_default_provider(provider),
        
        "default_model": lambda model:
            builder.set_default_model(model),
        
        # Built-in session filters
        "filters": {
            "last_n": lambda n: ("last_n", n),
            "token_budget": lambda max_tokens: ("token_budget", max_tokens),
            "by_role": lambda role: ("by_role", role),
            "compose": lambda *filters: ("compose", filters),
        },
        
        # Built-in spec matchers (thin wrappers, real logic in Behave steps)
        "contains": lambda value: ("contains", value),
        "equals": lambda value: ("equals", value),
        "matches": lambda pattern: ("matches", pattern),
    }
```

---

## 3. Pydantic AI Integration

### TactusContext (Dependencies)

```python
from pydantic import BaseModel
from pydantic_ai import RunContext


class TactusContext(BaseModel):
    """Runtime context passed via Pydantic AI dependencies."""
    
    model_config = {"arbitrary_types_allowed": True}
    
    params: dict[str, Any]
    state: "StatePrimitive"
    session: "SessionManager"
    procedure_id: str
    # Add more as needed


# Tools receive context via Pydantic AI dependency injection
async def create_tool_with_context(tool_name: str, tool_impl: Callable):
    """Wrap a tool function to receive TactusContext."""
    
    async def wrapped(ctx: RunContext[TactusContext], **kwargs):
        return await tool_impl(ctx.deps, **kwargs)
    
    return wrapped
```

### Template Resolution via Prepare

System prompts with `{params.topic}` markers are resolved using Pydantic AI's prepare mechanism:

```python
from pydantic_ai import Agent


def create_agent_with_templates(agent_decl: AgentDeclaration) -> Agent:
    """Create Pydantic AI agent with template resolution."""
    
    agent = Agent(
        model=agent_decl.model,
        deps_type=TactusContext,
        output_type=build_output_model(agent_decl.output) if agent_decl.output else None,
    )
    
    # If system_prompt is a string with markers, create prepare function
    if isinstance(agent_decl.system_prompt, str) and "{" in agent_decl.system_prompt:
        @agent.system_prompt
        async def dynamic_system_prompt(ctx: RunContext[TactusContext]) -> str:
            return resolve_template(agent_decl.system_prompt, ctx.deps)
    else:
        agent.system_prompt = agent_decl.system_prompt
    
    return agent


def resolve_template(template: str, context: TactusContext) -> str:
    """Resolve {params.x}, {state.y} markers in template string."""
    # Implementation uses regex or simple parser
    # Accesses context.params, context.state, etc.
    ...
```

### Agent Output Schema to Pydantic Model

```python
from pydantic import create_model


def build_output_model(schema: AgentOutputSchema) -> type[BaseModel]:
    """Convert DSL output schema to Pydantic model for output_type."""
    
    field_definitions = {}
    for field_name, field_decl in schema.fields.items():
        python_type = TYPE_MAP[field_decl.field_type]
        if field_decl.required:
            field_definitions[field_name] = (python_type, ...)
        else:
            field_definitions[field_name] = (Optional[python_type], None)
    
    return create_model("AgentOutput", **field_definitions)


TYPE_MAP = {
    ParameterType.STRING: str,
    ParameterType.NUMBER: float,
    ParameterType.BOOLEAN: bool,
    ParameterType.ARRAY: list,
    ParameterType.OBJECT: dict,
}
```

### Session/Message History per Agent

```python
from pydantic_ai.messages import ModelMessage


class SessionManager:
    """Manages per-agent message histories with filtering."""
    
    def __init__(self):
        self.histories: dict[str, list[ModelMessage]] = {}
        self.shared_history: list[ModelMessage] = []
    
    def get_history_for_agent(
        self, 
        agent_name: str, 
        session_config: SessionConfiguration,
        context: TactusContext
    ) -> list[ModelMessage]:
        """Get filtered message history for an agent."""
        
        # Determine source
        if session_config.source == "own":
            messages = self.histories.get(agent_name, [])
        elif session_config.source == "shared":
            messages = self.shared_history
        else:
            messages = self.histories.get(session_config.source, [])
        
        # Apply filter
        if session_config.filter:
            messages = self._apply_filter(messages, session_config.filter, context)
        
        return messages
    
    def _apply_filter(
        self, 
        messages: list[ModelMessage], 
        filter_spec: Any,
        context: TactusContext
    ) -> list[ModelMessage]:
        """Apply declarative or function filter."""
        
        if callable(filter_spec):
            # Lua function - call it with messages and context
            return filter_spec(messages, context)
        
        filter_type, filter_arg = filter_spec
        if filter_type == "last_n":
            return messages[-filter_arg:]
        elif filter_type == "token_budget":
            return self._filter_by_token_budget(messages, filter_arg)
        elif filter_type == "compose":
            result = messages
            for f in filter_arg:
                result = self._apply_filter(result, f, context)
            return result
        # ... other built-in filters
```

---

## 4. Runtime Modifications

### TactusRuntime Changes

```python
class TactusRuntime:
    """Main execution engine - now uses registry instead of YAML parser."""
    
    async def execute(
        self, 
        source: str,  # .tac file contents
        context: dict[str, Any]
    ) -> dict[str, Any]:
        
        # Phase 1: Parse declarations
        registry = self._parse_declarations(source)
        
        # Phase 2: Validate parameters against schema
        validated_params = self._validate_parameters(registry, context)
        
        # Phase 3: Setup agents, primitives, context
        tactus_context = self._setup_runtime(registry, validated_params)
        
        # Phase 4: Execute procedure function
        result = await self._execute_procedure(registry, tactus_context)
        
        # Phase 5: Validate output
        return self._validate_output(registry, result)
    
    def _parse_declarations(self, source: str) -> ProcedureRegistry:
        """Execute .tac to collect declarations."""
        
        builder = RegistryBuilder()
        
        # Create fresh sandbox
        sandbox = LuaSandbox()
        
        # Inject DSL stubs
        for name, stub in create_dsl_stubs(builder).items():
            sandbox.set_global(name, stub)
        
        # Execute file - declarations self-register
        sandbox.execute(source)
        
        # Validate and return registry
        result = builder.validate()
        if not result.valid:
            raise ValidationError(result.errors)
        
        for warning in result.warnings:
            logger.warning(warning.message)
        
        return result.registry
    
    def _setup_runtime(
        self, 
        registry: ProcedureRegistry, 
        params: dict
    ) -> TactusContext:
        """Setup agents and primitives for execution."""
        
        # Create context
        context = TactusContext(
            params=params,
            state=StatePrimitive(),
            session=SessionManager(),
            procedure_id=self.procedure_id,
        )
        
        # Create Pydantic AI agents
        self.agents = {}
        for agent_decl in registry.agents.values():
            self.agents[agent_decl.name] = create_agent_with_templates(agent_decl)
        
        # Inject primitives into sandbox for procedure execution
        self._inject_primitives(context, registry)
        
        return context
    
    def _inject_primitives(self, context: TactusContext, registry: ProcedureRegistry):
        """Inject State, Tool, Human, Log, Agent.turn() etc."""
        
        # Standard primitives
        self.sandbox.set_global("State", context.state)
        self.sandbox.set_global("Tool", self.tool_primitive)
        self.sandbox.set_global("Human", self.human_primitive)
        self.sandbox.set_global("Log", self.log_primitive)
        self.sandbox.set_global("params", context.params)
        # ... etc
        
        # Agent turn functions (Worker.turn(), Reviewer.turn(), etc.)
        for agent_name in registry.agents:
            capitalized = agent_name.capitalize()
            agent_primitive = self._create_agent_primitive(agent_name, context)
            self.sandbox.set_global(capitalized, agent_primitive)
    
    async def _execute_procedure(
        self, 
        registry: ProcedureRegistry, 
        context: TactusContext
    ) -> dict:
        """Call the stored procedure function."""
        
        # The procedure function was stored during declaration parsing
        procedure_fn = registry.procedure_function
        
        # Execute it (may be async via lupa coroutines)
        result = procedure_fn()
        
        return lua_table_to_dict(result)
```

### Delete These Files

- `tactus/core/yaml_parser.py` - Remove entirely
- Any YAML-specific validation code
- References to `.tyml` extension handling

---

## 5. ANTLR Grammar Approach

### Strategy: Semantic Layer on Lua 5.4

**Do NOT modify the Lua grammar.** Use the standard [Lua 5.4 grammar from antlr/grammars-v4](https://github.com/antlr/grammars-v4/tree/master/lua).

Build a **semantic analyzer** that walks the parse tree:

```
Parse Tree (ANTLR)
       │
       ▼
Semantic Visitor
       │
       ├── Recognizes: name "string"
       ├── Recognizes: parameter "name" { config }
       ├── Recognizes: agent "name" { config }
       ├── Recognizes: procedure(function() ... end)
       ├── Recognizes: specification "name" { scenarios }
       │
       ▼
DSL Declarations + Validation Messages
```

### Validation Modes

**Quick mode (IDE, real-time):**
- ANTLR parse only
- Recognize DSL constructs
- Basic structural validation
- Return immediately with syntax errors

**Full mode (CLI, pre-execution):**
- ANTLR parse
- Semantic validation
- Cross-reference checking (agent references valid tools, etc.)
- Return all errors and warnings

```python
class TactusValidator:
    def validate(self, source: str, mode: str = "full") -> ValidationResult:
        # Always run ANTLR
        parse_tree = self._antlr_parse(source)
        if parse_tree.errors:
            return ValidationResult(valid=False, errors=parse_tree.errors)
        
        if mode == "quick":
            return ValidationResult(valid=True)
        
        # Full mode: semantic analysis
        return self._semantic_validate(parse_tree)
```

### TypeScript Implementation (Web IDE)

```typescript
interface TactusDiagnostic {
  severity: "error" | "warning";
  message: string;
  range: { start: Position; end: Position };
}

class TactusLanguageService {
  validate(source: string): TactusDiagnostic[] {
    const tree = this.parser.parse(source);
    const visitor = new TactusDSLVisitor();
    return visitor.visit(tree);
  }
  
  getCompletions(source: string, position: Position): CompletionItem[] {
    // Context-aware completions based on DSL structure
  }
  
  getHover(source: string, position: Position): Hover | null {
    // Documentation for DSL constructs
  }
}
```

### Python Implementation (CLI)

```python
class TactusValidator(LuaParserVisitor):
    """Validates .tac files using ANTLR parse tree."""
    
    DSL_FUNCTIONS = {
        "name", "version", "description",
        "parameter", "output", "agent", "procedure",
        "prompt", "hitl", "stages", "specification",
        "default_provider", "default_model"
    }
    
    def visitFunctioncall(self, ctx):
        func_name = self._get_function_name(ctx)
        if func_name in self.DSL_FUNCTIONS:
            self._validate_dsl_call(func_name, ctx)
        return self.visitChildren(ctx)
```

---

## 6. BDD Specifications

### DSL Syntax

```lua
specification "greeting behavior" {
    scenario "greets with provided name" {
        given = { params = { name = "Alice" } },
        then_output = { greeting = contains("Alice") }
    },
    
    scenario "handles missing name gracefully" {
        given = { params = {} },
        then_output = { greeting = contains("friend") }
    },
    
    scenario "uses mocked search results" {
        given = { params = { topic = "AI" } },
        mocks = {
            search = { results = {"Result 1", "Result 2"} }
        },
        then_output = { findings = contains("Result 1") }
    }
}
```

### Compilation to Gherkin/Behave

The `specification` declaration compiles to Gherkin feature files:

```gherkin
# Generated: greeting_behavior.feature
Feature: greeting behavior

  Scenario: greets with provided name
    Given parameter "name" is "Alice"
    When the procedure executes
    Then output "greeting" contains "Alice"

  Scenario: handles missing name gracefully
    Given no parameters
    When the procedure executes
    Then output "greeting" contains "friend"

  Scenario: uses mocked search results
    Given parameter "topic" is "AI"
    And tool "search" returns {"results": ["Result 1", "Result 2"]}
    When the procedure executes
    Then output "findings" contains "Result 1"
```

### Behave Step Definitions

```python
# steps/tactus_steps.py

from behave import given, when, then
from tactus import TactusRuntime


@given('parameter "{name}" is "{value}"')
def step_set_parameter(context, name, value):
    context.params[name] = value


@given('tool "{tool_name}" returns {response}')
def step_mock_tool(context, tool_name, response):
    context.mocks[tool_name] = json.loads(response)


@when('the procedure executes')
def step_execute_procedure(context):
    runtime = TactusRuntime(
        procedure_id="test",
        tool_mocks=context.mocks
    )
    context.result = runtime.execute(
        context.procedure_source,
        context.params
    )


@then('output "{field}" contains "{value}"')
def step_check_output_contains(context, field, value):
    assert value in context.result[field]


@then('output "{field}" equals "{value}"')
def step_check_output_equals(context, field, value):
    assert context.result[field] == value
```

### Tool Mocking Integration

```python
class TactusRuntime:
    def __init__(
        self, 
        procedure_id: str,
        tool_mocks: Optional[dict[str, Any]] = None,
        ...
    ):
        self.tool_mocks = tool_mocks or {}
    
    def _create_tool(self, tool_name: str) -> Callable:
        if tool_name in self.tool_mocks:
            # Return mock instead of real implementation
            mock_response = self.tool_mocks[tool_name]
            async def mocked_tool(**kwargs):
                return mock_response
            return mocked_tool
        else:
            return self._get_real_tool(tool_name)
```

### CLI Commands

```bash
# Run specifications for a procedure
tactus test hello.tac

# Run with verbose output
tactus test hello.tac --verbose

# Generate Gherkin files without running
tactus test hello.tac --generate-only
```

---

## 7. Complete DSL Example

```lua
-- hello.tac

name "hello_world"
version "1.0.0"
description "A greeting procedure with research capability"

default_provider "openai"
default_model "gpt-4o"

-- Parameters
parameter "name" {
    type = "string",
    required = true,
    description = "Name of the person to greet"
}

parameter "include_research" {
    type = "boolean",
    default = false
}

-- Outputs
output "greeting" {
    type = "string",
    required = true
}

output "research_findings" {
    type = "string",
    required = false
}

-- Stages
stages { "greeting", "researching", "complete" }

-- Agents
agent "greeter" {
    system_prompt = [[
        You are a friendly greeter. Greet {params.name} warmly.
        When done, call the done tool with your greeting.
    ]],
    tools = {"done"},
    output = {
        message = { type = "string", required = true }
    }
}

agent "researcher" {
    model = "gpt-4o-mini",  -- Override default for cost savings
    system_prompt = [[
        Research interesting facts about the name: {params.name}
        Provide 2-3 interesting findings.
    ]],
    tools = {"search", "done"},
    session = {
        filter = filters.token_budget(50000)
    }
}

-- Procedure
procedure(function()
    Stage.set("greeting")
    
    repeat
        Greeter.turn()
    until Tool.called("done")
    
    local greeting = Tool.last_result("done")
    State.set("greeting", greeting)
    
    local findings = nil
    if params.include_research then
        Stage.set("researching")
        
        repeat
            Researcher.turn()
        until Tool.called("done") or Iterations.exceeded(10)
        
        findings = Tool.last_result("done")
    end
    
    Stage.set("complete")
    
    return {
        greeting = greeting,
        research_findings = findings
    }
end)

-- Specifications
specification "greeting behavior" {
    scenario "greets by name" {
        given = { params = { name = "Alice" } },
        mocks = {
            done = { reason = "Hello, Alice! Welcome!" }
        },
        then_output = { greeting = contains("Alice") }
    },
    
    scenario "includes research when requested" {
        given = { params = { name = "Alice", include_research = true } },
        mocks = {
            search = { results = {"Alice is a popular name"} },
            done = { reason = "Alice means noble" }
        },
        then_output = {
            greeting = contains("Alice"),
            research_findings = contains("noble")
        }
    }
}
```

---

## 8. Migration Path

### Converting .tyml to .tac

Create a migration script:

```python
# scripts/migrate_tyml.py

def migrate_tyml_to_tactus(tyml_content: str) -> str:
    """Convert YAML+Lua to pure Lua DSL."""
    
    parsed = yaml.safe_load(tyml_content)
    
    lines = []
    
    # Metadata
    lines.append(f'name "{parsed["name"]}"')
    lines.append(f'version "{parsed["version"]}"')
    if parsed.get("description"):
        lines.append(f'description [[{parsed["description"]}]]')
    lines.append("")
    
    # Parameters
    for param_name, param_config in parsed.get("params", {}).items():
        lines.append(f'parameter "{param_name}" {{')
        lines.append(f'    type = "{param_config["type"]}",')
        if "required" in param_config:
            lines.append(f'    required = {str(param_config["required"]).lower()},')
        if "default" in param_config:
            lines.append(f'    default = {lua_repr(param_config["default"])},')
        lines.append("}")
        lines.append("")
    
    # ... continue for outputs, agents, etc.
    
    # Procedure (already Lua)
    lines.append("procedure(function()")
    lines.append(indent(parsed["procedure"]))
    lines.append("end)")
    
    return "\n".join(lines)
```

### Files to Convert

All files in `examples/`:
- `hello-world.tyml` → `hello-world.tac`
- `simple-agent.tyml` → `simple-agent.tac`
- `state-management.tyml` → `state-management.tac`
- `with-parameters.tyml` → `with-parameters.tac`
- `multi-model.tyml` → `multi-model.tac`

### Files to Delete

- `tactus/core/yaml_parser.py`
- `ProcedureYAMLParser` class and all references
- Any `.tyml` handling code
- Example `.tyml` files after conversion

### Update Tests

All tests must use new `.tac` format. Update:
- `tests/integration/test_examples.py`
- Any test fixtures using YAML
- BDD feature files if any exist

---

## 9. Implementation Order

1. **Pydantic models** - `ProcedureRegistry`, declarations, validation
2. **RegistryBuilder** - DSL function registration
3. **DSL stubs** - Functions injected into lupa
4. **TactusRuntime refactor** - Use registry instead of YAML parser
5. **Template resolution** - Integrate with Pydantic AI prepare/dependencies
6. **Session management** - Per-agent history with filters
7. **Specification support** - DSL, Gherkin generation, Behave steps
8. **ANTLR validator** - Python CLI implementation
9. **Migration script** - Convert existing examples
10. **Delete YAML code** - Clean break
11. **Update all tests** - Everything passes with new format

---

## 10. Key Design Decisions Summary

| Decision | Choice | Rationale |
|----------|--------|-----------|
| File extension | `.tac` | Free syntax highlighting, distinctive |
| Template syntax | `{params.x}` in strings | Matches current, resolved via Pydantic AI prepare |
| Validation | Layered (quick + full) | IDE needs speed, CLI needs thoroughness |
| Warnings vs errors | Both supported | Missing specs = warning, missing name = error |
| Session/history | Per-agent with filters | Core DSL value proposition |
| Specs | Lua syntax → Gherkin → Behave | Leverage existing BDD ecosystem |
| Tool mocking | Built into runtime | Critical for deterministic testing |
| Backwards compatibility | None | Clean break, no fallbacks |

---

## 11. Open Questions for Implementation

1. **Lua coroutines** - How does `procedure_function` handle async? Does lupa support Python async inside Lua coroutines?

2. **Error locations** - How to map Lua runtime errors back to source lines for good error messages?

3. **Hot reload** - Should the runtime cache parsed registries, or always re-parse?

4. **Spec isolation** - Each scenario should run in isolation. How to reset state between scenarios?

5. **Filter composition** - The `filters.compose()` API needs careful design to be intuitive.