"""
DSL stub functions for Lua execution.

These functions are injected into the Lua sandbox before executing
.tactus.lua files. They populate the registry with declarations.
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


def create_dsl_stubs(builder: RegistryBuilder) -> dict[str, Callable]:
    """
    Create DSL stub functions that populate the registry.

    These functions are injected into the Lua environment before
    executing the .tactus.lua file.
    """

    def _name(value: str) -> None:
        """Set procedure name."""
        builder.set_name(value)

    def _version(value: str) -> None:
        """Set procedure version."""
        builder.set_version(value)

    def _description(value: str) -> None:
        """Set procedure description."""
        builder.set_description(value)

    def _parameter(param_name: str, config=None) -> None:
        """Register a parameter."""
        builder.register_parameter(param_name, lua_table_to_dict(config or {}))

    def _output(output_name: str, config=None) -> None:
        """Register an output field."""
        builder.register_output(output_name, lua_table_to_dict(config or {}))

    def _agent(agent_name: str, config) -> None:
        """Register an agent."""
        builder.register_agent(agent_name, lua_table_to_dict(config))

    def _procedure(lua_function) -> None:
        """Store procedure function for later execution."""
        builder.set_procedure(lua_function)

    def _prompt(prompt_name: str, content: str) -> None:
        """Register a prompt template."""
        builder.register_prompt(prompt_name, content)

    def _hitl(hitl_name: str, config) -> None:
        """Register a HITL interaction point."""
        builder.register_hitl(hitl_name, lua_table_to_dict(config))

    def _stages(*stage_names) -> None:
        """Register stage names."""
        builder.set_stages(list(stage_names))

    def _specification(spec_name: str, scenarios) -> None:
        """Register a BDD specification."""
        builder.register_specification(spec_name, lua_table_to_dict(scenarios))

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

    return {
        # Core declarations
        "name": _name,
        "version": _version,
        "description": _description,
        # Component declarations
        "parameter": _parameter,
        "output": _output,
        "agent": _agent,
        "procedure": _procedure,
        "prompt": _prompt,
        "hitl": _hitl,
        "stages": _stages,
        "specification": _specification,
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
