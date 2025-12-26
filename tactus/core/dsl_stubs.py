"""
DSL stub functions for Lua execution.

These functions are injected into the Lua sandbox before executing
.tac files. They populate the registry with declarations.
"""

from typing import Any, Callable

from .registry import RegistryBuilder


def lua_table_to_dict(lua_table):
    """
    Convert lupa table to Python dict or list recursively.

    Handles:
    - Nested tables
    - Arrays (tables with numeric indices)
    - Empty tables (converted to empty list)
    - Mixed tables
    - Primitive values
    """
    if lua_table is None:
        return {}

    # Check if it's a lupa table
    if not hasattr(lua_table, "items"):
        # It's a primitive value, return as-is
        return lua_table

    try:
        # Get all keys
        keys = list(lua_table.keys())

        # Empty table - return empty list (common for tools = {})
        if not keys:
            return []

        # Check if it's an array (all keys are consecutive integers starting from 1)
        if all(isinstance(k, int) for k in keys):
            sorted_keys = sorted(keys)
            if sorted_keys == list(range(1, len(keys) + 1)):
                # It's an array
                return [
                    (
                        lua_table_to_dict(lua_table[k])
                        if hasattr(lua_table[k], "items")
                        else lua_table[k]
                    )
                    for k in sorted_keys
                ]

        # It's a dictionary
        result = {}
        for key, value in lua_table.items():
            # Recursively convert nested tables
            if hasattr(value, "items"):
                result[key] = lua_table_to_dict(value)
            else:
                result[key] = value
        return result

    except (AttributeError, TypeError):
        # Fallback: return as-is
        return lua_table


def _normalize_schema(schema):
    """Convert empty list to empty dict (lua_table_to_dict converts {} to [])."""
    if isinstance(schema, list) and len(schema) == 0:
        return {}
    return schema


def create_dsl_stubs(builder: RegistryBuilder) -> dict[str, Callable]:
    """
    Create DSL stub functions that populate the registry.

    These functions are injected into the Lua environment before
    executing the .tac file.
    """
    # Global registry for named procedure stubs to find their implementations
    _procedure_registry = {}

    def _agent(agent_name: str, config) -> None:
        """Register an agent with its configuration."""
        config_dict = lua_table_to_dict(config)

        # NOTE: Inline tools (with 'handler' key) are kept in the 'tools' field
        # and will be processed by runtime during agent setup. We don't register
        # them in registry.lua_tools to avoid double-processing.

        # Extract output schema if present (support both 'output' and 'output_type')
        # output_type is preferred (aligned with pydantic-ai)
        output_schema = None
        if "output_type" in config_dict:
            output_config = config_dict["output_type"]
            if isinstance(output_config, dict):
                output_schema = output_config
        elif "output" in config_dict:
            output_config = config_dict["output"]
            if isinstance(output_config, dict):
                output_schema = output_config

        # Support 'session' as an alias for 'message_history'
        if "session" in config_dict and "message_history" not in config_dict:
            config_dict["message_history"] = config_dict["session"]

        builder.register_agent(agent_name, config_dict, output_schema)

    def _procedure(name, config_or_fn, fn=None):
        """
        Register a named procedure.

        Supports two syntaxes:
        1. procedure("name", {config}, function)  # with config
        2. procedure("name", function)            # without config

        Args:
            name: Procedure name (string)
            config_or_fn: Either config table or function
            fn: Function (if config_or_fn is config table)

        Returns:
            Stub that will be replaced with ProcedureCallable at runtime
        """
        # Validate first argument is a string
        if not isinstance(name, str):
            raise TypeError(
                f"procedure() first argument must be a string name, got {type(name).__name__}"
            )

        # Determine if we have config or just function
        if callable(config_or_fn) and not hasattr(config_or_fn, "items"):
            # procedure("name", function)
            config = {}
            fn = config_or_fn
        elif hasattr(config_or_fn, "items"):
            # procedure("name", {config}, function)
            if fn is None:
                raise TypeError(
                    "procedure() requires a function as the last argument when config is provided"
                )
            config = lua_table_to_dict(config_or_fn)
            # Normalize empty config (lua {} -> python [])
            config = _normalize_schema(config)
        else:
            raise TypeError(
                f"procedure() second argument must be config table or function, "
                f"got {type(config_or_fn).__name__}"
            )

        # Extract schemas (normalize empty lists to dicts)
        input_schema = _normalize_schema(config.get("input", {}))
        output_schema = _normalize_schema(config.get("output", {}))
        state_schema = _normalize_schema(config.get("state", {}))

        # Register named procedure
        builder.register_named_procedure(name, fn, input_schema, output_schema, state_schema)

        # Return a stub that will delegate to the registry at call time
        class NamedProcedureStub:
            """
            Stub that delegates to the actual ProcedureCallable when called.
            This gets replaced during runtime initialization.
            """

            def __init__(self, proc_name, registry):
                self.name = proc_name
                self.registry = registry

            def __call__(self, *args):
                # Look up the real implementation from the registry
                if self.name in self.registry:
                    return self.registry[self.name](*args)
                else:
                    raise RuntimeError(f"Named procedure '{self.name}' not initialized yet")

        stub = NamedProcedureStub(name, _procedure_registry)
        _procedure_registry[name] = stub  # Store stub temporarily
        return stub

    def _prompt(prompt_name: str, content: str) -> None:
        """Register a prompt template."""
        builder.register_prompt(prompt_name, content)

    def _toolset(toolset_name: str, config) -> None:
        """Register a toolset definition."""
        builder.register_toolset(toolset_name, lua_table_to_dict(config))

    def _tool(tool_name: str, config, handler_fn) -> None:
        """Register an individual Lua tool.

        Args:
            tool_name: Name of the tool
            config: Table with description, parameters
            handler_fn: Lua function to call when tool is invoked
        """
        config_dict = lua_table_to_dict(config)
        builder.register_tool(tool_name, config_dict, handler_fn)

    def _hitl(hitl_name: str, config) -> None:
        """Register a HITL interaction point."""
        builder.register_hitl(hitl_name, lua_table_to_dict(config))

    def _model(model_name: str, config) -> None:
        """Register a model for ML inference."""
        builder.register_model(model_name, lua_table_to_dict(config))

    def _stages(*stage_names) -> None:
        """Register stage names."""
        # Handle both stages("a", "b", "c") and stages({"a", "b", "c"})
        if len(stage_names) == 1 and hasattr(stage_names[0], "items"):
            # Single Lua table argument - convert it
            stages_list = lua_table_to_dict(stage_names[0])
        else:
            # Multiple string arguments
            stages_list = list(stage_names)
        builder.set_stages(stages_list)

    def _specification(spec_name: str, scenarios) -> None:
        """Register a BDD specification."""
        builder.register_specification(spec_name, lua_table_to_dict(scenarios))

    def _specifications(gherkin_text: str) -> None:
        """Register Gherkin BDD specifications."""
        builder.register_specifications(gherkin_text)

    def _step(step_text: str, lua_function) -> None:
        """Register a custom step definition."""
        builder.register_custom_step(step_text, lua_function)

    def _evaluation(config) -> None:
        """Set evaluation configuration."""
        builder.set_evaluation_config(lua_table_to_dict(config or {}))

    def _evaluations(config) -> None:
        """Register Pydantic Evals evaluation configuration."""
        builder.register_evaluations(lua_table_to_dict(config or {}))

    def _default_provider(provider: str) -> None:
        """Set default provider."""
        builder.set_default_provider(provider)

    def _default_model(model: str) -> None:
        """Set default model."""
        builder.set_default_model(model)

    def _return_prompt(prompt: str) -> None:
        """Set return prompt."""
        builder.set_return_prompt(prompt)

    def _error_prompt(prompt: str) -> None:
        """Set error prompt."""
        builder.set_error_prompt(prompt)

    def _status_prompt(prompt: str) -> None:
        """Set status prompt."""
        builder.set_status_prompt(prompt)

    def _async(enabled: bool) -> None:
        """Set async execution flag."""
        builder.set_async(enabled)

    def _max_depth(depth: int) -> None:
        """Set maximum recursion depth."""
        builder.set_max_depth(depth)

    def _max_turns(turns: int) -> None:
        """Set maximum turns."""
        builder.set_max_turns(turns)

    # Built-in session filters
    def _last_n(n: int) -> tuple:
        """Filter to keep last N messages."""
        return ("last_n", n)

    def _token_budget(max_tokens: int) -> tuple:
        """Filter by token budget."""
        return ("token_budget", max_tokens)

    def _by_role(role: str) -> tuple:
        """Filter by message role."""
        return ("by_role", role)

    def _compose(*filters) -> tuple:
        """Compose multiple filters."""
        return ("compose", filters)

    # Built-in spec matchers
    def _contains(value: Any) -> tuple:
        """Matcher: contains value."""
        return ("contains", value)

    def _equals(value: Any) -> tuple:
        """Matcher: equals value."""
        return ("equals", value)

    def _matches(pattern: str) -> tuple:
        """Matcher: matches regex pattern."""
        return ("matches", pattern)

    def _input(schema) -> None:
        """
        Top-level input schema declaration for script mode.

        Used when there's no explicit main procedure - defines input
        for the top-level script code.

        Example:
            input {
                query = {type = "string", required = true},
                limit = {type = "number", default = 10}
            }
        """
        schema_dict = lua_table_to_dict(schema)
        builder.register_top_level_input(schema_dict)

    def _output(schema) -> None:
        """
        Top-level output schema declaration for script mode.

        Used when there's no explicit main procedure - defines output
        for the top-level script code.

        Example:
            output {
                result = {type = "string", required = true},
                count = {type = "number", required = true}
            }
        """
        schema_dict = lua_table_to_dict(schema)
        builder.register_top_level_output(schema_dict)

    return {
        # Core declarations
        # Component declarations
        "agent": _agent,
        "model": _model,
        "procedure": _procedure,
        "prompt": _prompt,
        "toolset": _toolset,
        "tool": _tool,
        "hitl": _hitl,
        "stages": _stages,
        "specification": _specification,
        # BDD Testing
        "specifications": _specifications,
        "step": _step,
        "evaluation": _evaluation,
        # Pydantic Evals Integration
        "evaluations": _evaluations,
        # Script mode (top-level declarations)
        "input": _input,
        "output": _output,
        # Settings
        "default_provider": _default_provider,
        "default_model": _default_model,
        "return_prompt": _return_prompt,
        "error_prompt": _error_prompt,
        "status_prompt": _status_prompt,
        "async": _async,
        "max_depth": _max_depth,
        "max_turns": _max_turns,
        # Built-in filters (exposed as a table)
        "filters": {
            "last_n": _last_n,
            "token_budget": _token_budget,
            "by_role": _by_role,
            "compose": _compose,
        },
        # Built-in matchers
        "contains": _contains,
        "equals": _equals,
        "matches": _matches,
    }
