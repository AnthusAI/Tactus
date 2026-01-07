"""
DSL stub functions for Lua execution.

These functions are injected into the Lua sandbox before executing
.tac files. They populate the registry with declarations.

New Syntax (curried functions):
    agent "greeter" { config }      -- agent(name)(config)
    tool "done" { handler = fn }    -- tool(name)(config)
    procedure "main" { run = fn }   -- procedure(name)(config)
    model "classifier" { config }   -- model(name)(config)

Lookup functions:
    Agent("greeter").turn()         -- Look up and use agent
    Tool("done")({args})            -- Look up and call tool
    Model("classifier").predict()   -- Look up and use model
"""

from typing import Any, Callable, Dict

from .registry import RegistryBuilder
from tactus.primitives.handles import AgentHandle, ModelHandle, AgentLookup, ModelLookup


# NEW Builder pattern for field types - moved outside function for import
class FieldDefinition(dict):
    """Special marker class for new field.type{} syntax."""

    pass


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


def create_dsl_stubs(builder: RegistryBuilder, tool_primitive: Any = None) -> dict[str, Callable]:
    """
    Create DSL stub functions that populate the registry.

    These functions are injected into the Lua environment before
    executing the .tac file.

    Args:
        builder: RegistryBuilder to register declarations
        tool_primitive: Optional ToolPrimitive for creating callable ToolHandles

    Returns:
        Dict of DSL functions to inject into Lua, including:
        - Lowercase definition functions: agent, tool, procedure, model
        - Uppercase lookup functions: Agent, Tool, Model
    """
    # Registries for handle lookup
    _agent_registry: Dict[str, AgentHandle] = {}
    _tool_registry: Dict[str, Any] = {}  # ToolHandle instances
    _model_registry: Dict[str, ModelHandle] = {}

    # Global registry for named procedure stubs to find their implementations
    _procedure_registry = {}

    def _agent(agent_name: str, config=None):
        """
        Agent definition supporting both old and new syntax.

        Old syntax (deprecated):
            agent("name", {config})

        New syntax (curried):
            agent "name" { config }

        Args:
            agent_name: Agent name (string identifier)
            config: Optional config dict (for old syntax)

        Returns:
            Function that accepts config (new syntax) or AgentHandle (old syntax)
        """
        # Check if this is old-style 2-argument call
        if config is not None:
            # Old syntax: agent("name", {config})
            config_dict = lua_table_to_dict(config)

            # NOTE: Inline tools (with 'handler' key) are kept in the 'tools' field
            # and will be processed by runtime during agent setup. We don't register
            # them in registry.lua_tools to avoid double-processing.

            # Extract output schema if present (support both 'output' and 'output')
            # output is preferred (aligned with pydantic-ai)
            output_schema = None
            if "output" in config_dict:
                output_config = config_dict["output"]
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

            # Create and register handle for lookup
            handle = AgentHandle(agent_name)
            _agent_registry[agent_name] = handle
            return handle

        # New curried syntax - return a function that accepts config
        def accept_config(config) -> AgentHandle:
            """Accept config and register agent."""
            config_dict = lua_table_to_dict(config)

            # NOTE: Inline tools (with 'handler' key) are kept in the 'tools' field
            # and will be processed by runtime during agent setup. We don't register
            # them in registry.lua_tools to avoid double-processing.

            # Extract output schema if present (support both 'output' and 'output')
            # output is preferred (aligned with pydantic-ai)
            output_schema = None
            if "output" in config_dict:
                output_config = config_dict["output"]
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

            # Create and register handle for lookup
            handle = AgentHandle(agent_name)
            _agent_registry[agent_name] = handle
            return handle

        return accept_config

    def _procedure(name: str, config=None, run_fn=None):
        """
        Procedure definition supporting both old and new syntax.

        Old syntax (deprecated):
            procedure("main", {config}, function() ... end)

        New syntax (curried):
            procedure "main" { config with function as last element }

        Args:
            name: Procedure name (string)
            config: Optional config dict (for old syntax)
            run_fn: Optional function (for old syntax)

        Returns:
            Function that accepts config (new syntax) or ProcedureStub (old syntax)

        Example (New Lua):
            procedure "main" {
                input = {...},
                output = {...},
                function(input)
                    -- procedure body uses explicit input parameter
                    return {result = input.value * 2}
                end
            }

        Example (Old Lua - deprecated):
            procedure("main", {
                input = {...},
                output = {...}
            }, function(input)
                -- procedure body uses explicit input parameter
                return {result = input.value * 2}
            end)
        """
        # Validate first argument is a string
        if not isinstance(name, str):
            raise TypeError(
                f"procedure() first argument must be a string name, got {type(name).__name__}"
            )

        # Check if this is old-style 3-argument call
        if config is not None or run_fn is not None:
            # Old syntax: procedure("name", {config}, function)
            # Convert config if needed
            if config is not None:
                config_dict = lua_table_to_dict(config)
            else:
                config_dict = {}

            # Normalize empty config (lua {} -> python [])
            if isinstance(config_dict, list) and len(config_dict) == 0:
                config_dict = {}

            if run_fn is None:
                raise TypeError(
                    f"procedure '{name}' requires a function in old syntax. "
                    f"Use: procedure('{name}', {{config}}, function() ... end)"
                )

            # Extract schemas (normalize empty lists to dicts)
            input_schema = _normalize_schema(config_dict.get("input", {}))
            output_schema = _normalize_schema(config_dict.get("output", {}))
            state_schema = _normalize_schema(config_dict.get("state", {}))

            # Register named procedure
            builder.register_named_procedure(
                name, run_fn, input_schema, output_schema, state_schema
            )

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

        # New curried syntax - return a function that accepts config
        def accept_config(config):
            """Accept config (with function as last unnamed element) and register procedure."""
            # First extract the function from the raw Lua table before conversion
            # In Lua tables, unnamed elements are stored with numeric indices (1-based)
            run_fn = None

            # Check for function in array part of table (numeric indices)
            if hasattr(config, "__getitem__"):
                # Try to get function from numeric indices (Lua uses 1-based indexing)
                for i in range(1, 10):  # Check first few positions
                    try:
                        item = config[i]
                        if callable(item):
                            run_fn = item
                            # Remove from table so it doesn't appear in config_dict
                            config[i] = None
                            break
                    except (KeyError, TypeError):
                        break

            # Now convert to dict (excluding the function we removed)
            config_dict = lua_table_to_dict(config)
            # Normalize empty config (lua {} -> python [])
            if isinstance(config_dict, list) and len(config_dict) == 0:
                config_dict = {}

            # If we got a list with None values from removing function, clean it up
            if isinstance(config_dict, list):
                config_dict = [x for x in config_dict if x is not None]
                if len(config_dict) == 0:
                    config_dict = {}

            # If no function found in array part, check for legacy 'run' field
            if run_fn is None:
                run_fn = config_dict.pop("run", None)

            if run_fn is None:
                raise TypeError(
                    f"procedure '{name}' requires a function. "
                    f'Use: procedure "{name}" {{ input = {{...}}, function() ... end }}'
                )

            # Extract schemas (normalize empty lists to dicts)
            input_schema = _normalize_schema(config_dict.get("input", {}))
            output_schema = _normalize_schema(config_dict.get("output", {}))
            state_schema = _normalize_schema(config_dict.get("state", {}))

            # Register named procedure
            builder.register_named_procedure(
                name, run_fn, input_schema, output_schema, state_schema
            )

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

        return accept_config

    def _prompt(prompt_name: str, content: str) -> None:
        """Register a prompt template."""
        builder.register_prompt(prompt_name, content)

    def _toolset(toolset_name: str, config=None):
        """
        Toolset definition supporting both old and new syntax.

        Old syntax (deprecated):
            Toolset("name", {config})

        New syntax (curried):
            Toolset "name" { config }

        Supports multiple sources:
        - Import all tools from a .tac file via use = "./helpers/math.tac"
        - MCP server collection via use = "mcp.filesystem"
        - Group existing tools via tools = ["tool1", "tool2"]

        Args:
            toolset_name: Name of the toolset
            config: Optional config dict (for old syntax)

        Returns:
            Function that accepts config (new syntax) or None (old syntax)

        Example (Import from file):
            Toolset "math" { use = "./helpers/math.tac" }

        Example (MCP server):
            Toolset "filesystem" {
                use = "mcp.filesystem",
                include = {"read_file", "write_file"},  -- optional filter
                exclude = {"delete_file"}               -- optional filter
            }

        Example (Group existing tools):
            Toolset "research" {
                tools = {"search", "analyze", "summarize"}
            }

        Example (Inline Lua tools):
            Toolset "custom" {
                tools = {
                    {
                        name = "my_tool",
                        description = "A custom tool",
                        input = {text = field.string{required = true}},
                        function(args) return args.text:upper() end
                    }
                }
            }
        """
        # Check if this is old-style 2-argument call
        if config is not None:
            # Old syntax: Toolset("name", {config})
            config_dict = lua_table_to_dict(config)

            # Normalize empty config
            if isinstance(config_dict, list) and len(config_dict) == 0:
                config_dict = {}

            # Register the toolset
            builder.register_toolset(toolset_name, config_dict)
            return None

        # New curried syntax - return a function that accepts config
        def accept_config(config):
            """Accept config and register toolset."""
            config_dict = lua_table_to_dict(config)

            # Normalize empty config
            if isinstance(config_dict, list) and len(config_dict) == 0:
                config_dict = {}

            # Register the toolset
            builder.register_toolset(toolset_name, config_dict)

        return accept_config

    def _tool(tool_name: str, config=None, handler_fn=None):
        """
        Tool definition supporting both old and new syntax.

        Old syntax (deprecated):
            Tool("name", {config}, function)

        New syntax (curried):
            Tool "name" { config with function as last element }

        Supports multiple sources:
        - Inline Lua function (original behavior)
        - Standard library via use = "tactus.done"
        - Local .tac file via use = "./helpers/math.tac"
        - MCP server via use = "mcp.brave-search"
        - Python plugin via use = "plugin.financial.mortgage"
        - CLI executable via use = "cli.git"

        Args:
            tool_name: Name of the tool (used for tracking and agent toolsets)
            config: Optional config dict (for old syntax)
            handler_fn: Optional handler function (for old syntax)

        Returns:
            Function that accepts config and returns ToolHandle (new syntax) or ToolHandle (old syntax)

        Example (Inline Lua):
            Tool "done" {
                description = "Signal completion",
                input = {
                    reason = field.string{required = true}
                },
                function(input)
                    return {message = "Done: " .. input.reason}
                end
            }

        Example (Standard Library):
            Tool "done" { use = "tactus.done" }

        Example (Local file):
            Tool "math" { use = "./helpers/math.tac" }
        """
        from tactus.primitives.tool_handle import ToolHandle

        # Check if this is old-style 2 or 3-argument call
        if config is not None or handler_fn is not None:
            # Old syntax: Tool("name", {config}, function) or Tool("name", {config})
            config_dict = lua_table_to_dict(config) if config is not None else {}

            # Normalize empty config
            if isinstance(config_dict, list) and len(config_dict) == 0:
                config_dict = {}

            # Check for 'use' attribute to import from external source
            use_source = config_dict.get("use")
            if use_source:
                # This is an import, not an inline definition
                config_dict["source"] = use_source

                # For now, create a placeholder handler that will be replaced at runtime
                def placeholder_handler(input):
                    raise RuntimeError(
                        f"Tool '{tool_name}' from source '{use_source}' not loaded. "
                        "The runtime should have replaced this placeholder."
                    )

                handler_fn = placeholder_handler
            else:
                # Inline definition - check for handler in config or as third argument
                if handler_fn is None:
                    handler_fn = config_dict.pop("handler", None)

                if handler_fn is None:
                    raise TypeError(
                        f"Tool '{tool_name}' requires either a function or 'use' attribute."
                    )

            # Register in builder (for agent toolsets)
            import logging

            logger = logging.getLogger(__name__)
            logger.debug(f"Registering tool '{tool_name}' with config: {config_dict}")
            builder.register_tool(tool_name, config_dict, handler_fn)

            # Create and register handle for lookup
            handle = ToolHandle(tool_name, handler_fn, tool_primitive)
            _tool_registry[tool_name] = handle
            return handle

        # New curried syntax - return a function that accepts config
        def accept_config(config):
            """Accept config (with function as last unnamed element) and register tool."""
            # First extract the function from the raw Lua table before conversion
            handler_fn = None

            # Check for function in array part of table (numeric indices)
            if hasattr(config, "__getitem__"):
                # Try to get function from numeric indices (Lua uses 1-based indexing)
                for i in range(1, 10):  # Check first few positions
                    try:
                        item = config[i]
                        if callable(item):
                            handler_fn = item
                            # Remove from table so it doesn't appear in config_dict
                            config[i] = None
                            break
                    except (KeyError, TypeError):
                        break

            # Now convert to dict (excluding the function we removed)
            config_dict = lua_table_to_dict(config)

            # If we got a list with None values from removing function, clean it up
            if isinstance(config_dict, list):
                config_dict = [x for x in config_dict if x is not None]
                if len(config_dict) == 0:
                    config_dict = {}

            # Check for 'use' attribute to import from external source
            use_source = config_dict.get("use")
            if use_source:
                # This is an import, not an inline definition
                # The runtime will handle loading from the source
                config_dict["source"] = use_source

                # For now, create a placeholder handler that will be replaced at runtime
                def placeholder_handler(input):
                    raise RuntimeError(
                        f"Tool '{tool_name}' from source '{use_source}' not loaded. "
                        "The runtime should have replaced this placeholder."
                    )

                handler_fn = placeholder_handler
            else:
                # Inline definition - must have a function
                # If no function found in array part, check for legacy 'handler' field
                if handler_fn is None:
                    handler_fn = config_dict.pop("handler", None)

                if handler_fn is None:
                    raise TypeError(
                        f"Tool '{tool_name}' requires either a function or 'use' attribute. "
                        f'Use: Tool "{tool_name}" {{ function(input) ... end }} or '
                        f'Tool "{tool_name}" {{ use = "tactus.done" }}'
                    )

            # Register in builder (for agent toolsets)
            import logging

            logger = logging.getLogger(__name__)
            logger.debug(f"Registering tool '{tool_name}' with config: {config_dict}")
            builder.register_tool(tool_name, config_dict, handler_fn)

            # Create and register handle for lookup
            handle = ToolHandle(tool_name, handler_fn, tool_primitive)
            _tool_registry[tool_name] = handle
            return handle

        return accept_config

    def _hitl(hitl_name: str, config) -> None:
        """Register a HITL interaction point."""
        builder.register_hitl(hitl_name, lua_table_to_dict(config))

    def _model(model_name: str):
        """
        Curried model definition: model "name" { config }

        First call captures name, returns config acceptor.

        Args:
            model_name: Model name (string identifier)

        Returns:
            Function that accepts config and returns ModelHandle

        Example (Lua):
            classifier = model "classifier" {
                type = "pytorch",
                path = "models/classifier.pt"
            }

            local result = Model("classifier").predict(data)
        """

        def accept_config(config) -> ModelHandle:
            """Accept config and register model."""
            config_dict = lua_table_to_dict(config)
            builder.register_model(model_name, config_dict)

            # Create and register handle for lookup
            handle = ModelHandle(model_name)
            _model_registry[model_name] = handle
            return handle

        return accept_config

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

    # Type shorthand helper functions
    # OLD type functions - keeping temporarily until examples are updated
    def _required(type_name: str, description: str = None) -> dict:
        """Create a required field of given type."""
        result = {"type": type_name, "required": True}
        if description:
            result["description"] = description
        return result

    def _string(default: str = None, description: str = None) -> dict:
        """Create an optional string field."""
        result = {"type": "string", "required": False}
        if default is not None:
            result["default"] = default
        if description:
            result["description"] = description
        return result

    def _number(default: float = None, description: str = None) -> dict:
        """Create an optional number field."""
        result = {"type": "number", "required": False}
        if default is not None:
            result["default"] = default
        if description:
            result["description"] = description
        return result

    def _boolean(default: bool = None, description: str = None) -> dict:
        """Create an optional boolean field."""
        result = {"type": "boolean", "required": False}
        if default is not None:
            result["default"] = default
        if description:
            result["description"] = description
        return result

    def _array(default: list = None, description: str = None) -> dict:
        """Create an optional array field."""
        result = {"type": "array", "required": False}
        if default is not None:
            result["default"] = default if default else []
        if description:
            result["description"] = description
        return result

    def _object(default: dict = None, description: str = None) -> dict:
        """Create an optional object field."""
        result = {"type": "object", "required": False}
        if default is not None:
            result["default"] = default if default else {}
        if description:
            result["description"] = description
        return result

    # NEW Builder pattern for field types
    def _field_builder(field_type: str):
        """Create a field builder for the given type."""

        def build_field(options=None):
            """Build a field with the given options."""
            if options is None:
                options = {}

            # Convert Lua table to dict if needed
            if hasattr(options, "items"):
                options = lua_table_to_dict(options)

            # Create a FieldDefinition (subclass of dict) to mark new syntax
            result = FieldDefinition()
            result["type"] = field_type

            # Add required flag (default to false)
            result["required"] = options.get("required", False)

            # Add default value if provided and not required
            if "default" in options and not result["required"]:
                result["default"] = options["default"]

            # Add description if provided
            if "description" in options:
                result["description"] = options["description"]

            return result

        return build_field

    # Create the field table with builders for each type
    field = {
        "string": _field_builder("string"),
        "number": _field_builder("number"),
        "boolean": _field_builder("boolean"),
        "array": _field_builder("array"),
        "object": _field_builder("object"),
        "integer": _field_builder("integer"),
    }

    # Create lookup functions for uppercase names (Agent, Model)
    # These allow: Agent("greeter").turn(), Model("classifier").predict()
    _Agent = AgentLookup(_agent_registry)
    _Model = ModelLookup(_model_registry)

    # For Tool lookup, we'll add __call__ to ToolPrimitive
    # Set the tool registry on the primitive so it can do lookups
    if tool_primitive is not None:
        tool_primitive.set_tool_registry(_tool_registry)

    # Create hybrid functions that handle both definition and lookup
    class HybridAgent:
        """Callable that handles both Agent definition and lookup."""

        def __init__(self, definer, lookup):
            self.definer = definer
            self.lookup = lookup

        def __call__(self, name, config=None):
            # If config is provided, it's old-style definition: Agent("name", {config})
            if config is not None:
                return self.definer(name, config)

            # If called with just a string
            if isinstance(name, str):
                # Check if the agent is already defined (lookup case)
                if self.lookup and name in self.lookup._registry:
                    # This is a lookup: Agent("name") where agent exists
                    return self.lookup(name)
                else:
                    # This is the start of a definition: Agent "name" {...}
                    # Return the curried function from definer
                    return self.definer(name)

            # Otherwise pass through to definer
            return self.definer(name, config)

    class HybridModel:
        """Callable that handles both Model definition and lookup."""

        def __init__(self, definer, lookup):
            self.definer = definer
            self.lookup = lookup

        def __call__(self, name, config=None):
            # If config is provided, it's old-style definition: Model("name", {config})
            if config is not None:
                return self.definer(name, config)

            # If called with just a string
            if isinstance(name, str):
                # Check if the model is already defined (lookup case)
                if self.lookup and name in self.lookup._registry:
                    # This is a lookup: Model("name") where model exists
                    return self.lookup(name)
                else:
                    # This is the start of a definition: Model "name" {...}
                    # Return the curried function from definer
                    return self.definer(name)

            # Otherwise pass through to definer
            return self.definer(name, config)

    def _signature(sig_input, config=None):
        """
        Create a DSPy Signature.

        Supports both string format and structured format.

        String format:
        - Simple: "question -> answer"
        - Multi-field: "context, question -> reasoning, answer"
        - Typed: "question: str -> answer: str"

        Structured format (curried):
        - Signature "name" { input = {...}, output = {...} }

        Args:
            sig_input: Signature string like "question -> answer" or name for curried form
            config: Optional config dict (for structured form)

        Returns:
            A dspy.Signature class

        Example (Lua):
            -- String form
            Signature("question -> answer")
            Signature("context, question -> reasoning, answer")

            -- Structured form
            Signature "qa" {
                input = {
                    question = field.string{description = "The question to answer"}
                },
                output = {
                    answer = field.string{description = "The answer"}
                }
            }
        """
        from tactus.dspy import create_signature

        # String form - check if it looks like a signature string (contains "->")
        if isinstance(sig_input, str):
            if "->" in sig_input:
                # This is a signature string like "question -> answer"
                return create_signature(sig_input)
            else:
                # This is a name for curried form: Signature "name" {...}
                def accept_config(cfg):
                    """Accept config and create structured signature."""
                    config_dict = lua_table_to_dict(cfg)

                    # Normalize empty config
                    if isinstance(config_dict, list) and len(config_dict) == 0:
                        config_dict = {}

                    return create_signature(config_dict, name=sig_input)

                return accept_config

        # Direct dict form: Signature({ input = {...}, output = {...} })
        if hasattr(sig_input, "items"):
            config_dict = lua_table_to_dict(sig_input)
            return create_signature(config_dict)

        raise TypeError(
            f"Signature expects a string like 'input -> output' or a name for structured form, "
            f"got {type(sig_input).__name__}"
        )

    def _lm(model: str, config=None):
        """
        Configure Language Model for DSPy operations.

        Uses LiteLLM's model naming convention:
        - OpenAI: "openai/gpt-4o", "openai/gpt-4o-mini"
        - Anthropic: "anthropic/claude-3-5-sonnet-20241022"
        - AWS Bedrock: "bedrock/anthropic.claude-3-5-sonnet-20240620-v1:0"
        - Google: "gemini/gemini-pro"

        Args:
            model: Model identifier in LiteLLM format
            config: Optional configuration dict (temperature, api_key, etc.)

        Returns:
            Configured LM instance

        Example (Lua):
            LM("openai/gpt-4o")
            LM("openai/gpt-4o", { temperature = 0.7 })
            LM "anthropic/claude-3-5-sonnet-20241022" { temperature = 0.3 }
        """
        from tactus.dspy import configure_lm

        # Check if this is curried syntax (config is None, return acceptor)
        if config is None:
            # Return a function that accepts config
            def accept_config(cfg=None):
                cfg_dict = lua_table_to_dict(cfg) if cfg else {}
                return configure_lm(model, **cfg_dict)

            # Also allow immediate call without config
            # This handles: LM("openai/gpt-4o") with no second arg
            return accept_config

        # Direct call with config: LM("model", {config})
        config_dict = lua_table_to_dict(config)
        return configure_lm(model, **config_dict)

    def _mocks(config):
        """
        Define mock configurations for tools.

        Example usage:
            Mocks {
                search = {
                    returns = {results = {"mocked result"}}
                },
                get_time = {
                    temporal = {
                        {time = "10:00"},
                        {time = "11:00"},
                        {time = "12:00"}
                    }
                },
                translate = {
                    conditional = {
                        {when = {text = "hello"}, returns = {translation = "hola"}},
                        {when = {text = "goodbye"}, returns = {translation = "adiós"}}
                    }
                }
            }

        Args:
            config: Lua table containing mock definitions
        """
        if config is None:
            return

        config_dict = lua_table_to_dict(config)

        # Register mock configurations with the builder
        for tool_name, mock_config in config_dict.items():
            if not isinstance(mock_config, dict):
                continue

            # Convert DSL syntax to MockConfig format
            processed_config = {}

            # Static mocking with 'returns' key
            if "returns" in mock_config:
                processed_config["output"] = mock_config["returns"]

            # Temporal mocking
            elif "temporal" in mock_config:
                processed_config["temporal"] = mock_config["temporal"]

            # Conditional mocking
            elif "conditional" in mock_config:
                # Convert DSL conditional format to MockManager format
                conditionals = []
                for cond in mock_config["conditional"]:
                    if isinstance(cond, dict) and "when" in cond and "returns" in cond:
                        conditionals.append({"when": cond["when"], "return": cond["returns"]})
                processed_config["conditional_mocks"] = conditionals

            # Error simulation
            elif "error" in mock_config:
                processed_config["error"] = mock_config["error"]

            # Register the mock configuration
            builder.register_mock(tool_name, processed_config)

    def _history(messages=None):
        """
        Create a History for managing conversation messages.

        History is used to track multi-turn conversations and can be
        passed to Modules as an input field.

        Returns an object with methods:
        - add(message): Add a message to history
        - get(): Get all messages
        - clear(): Clear all messages

        Example (Lua):
            -- Create history
            local history = History()

            -- Add messages
            history.add({ question = "What is 2+2?", answer = "4" })

            -- Get messages
            local messages = history.get()

            -- Clear
            history.clear()
        """
        from tactus.dspy import create_history

        if messages is not None:
            messages_list = lua_table_to_dict(messages)
            return create_history(messages_list)
        return create_history()

    def _module(module_name: str, config=None):
        """
        Create a DSPy Module with a given strategy.

        Supports curried syntax: Module "name" { signature = "...", strategy = "predict" }

        Strategies:
        - "predict": Direct prediction using dspy.Predict
        - "chain_of_thought": Reasoning with dspy.ChainOfThought

        Args:
            module_name: Name for this module (used for tracking)
            config: Optional config dict (for old syntax)

        Returns:
            A callable TactusModule instance

        Example (Lua):
            -- Create a module
            local qa = Module "qa" {
                signature = "question -> answer",
                strategy = "predict"
            }

            -- Call the module
            local result = qa({ question = "What is 2+2?" })
            -- result.answer == "4"
        """
        from tactus.dspy import create_module

        # Check if this is old-style 2-argument call
        if config is not None:
            config_dict = lua_table_to_dict(config)
            return create_module(module_name, config_dict)

        # New curried syntax - return a function that accepts config
        def accept_config(cfg):
            """Accept config and create module."""
            config_dict = lua_table_to_dict(cfg)
            return create_module(module_name, config_dict)

        return accept_config

    return {
        # Core declarations (CamelCase - for definitions AND lookups)
        "Agent": HybridAgent(_agent, _Agent),
        "Model": HybridModel(_model, _Model),
        "Procedure": _procedure,
        "Prompt": _prompt,
        "Toolset": _toolset,
        "Tool": _tool,
        "Hitl": _hitl,
        "Stages": _stages,
        "Specification": _specification,
        # BDD Testing
        "Specifications": _specifications,
        "Step": _step,
        "Evaluation": _evaluation,
        # Pydantic Evals Integration
        "Evaluations": _evaluations,
        # Mocking
        "Mocks": _mocks,
        # DSPy Integration
        "LM": _lm,
        "Signature": _signature,
        "Module": _module,
        "History": _history,
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
        # New field builder pattern
        "field": field,
        # Old type functions (temporary until migration)
        "required": _required,
        "string": _string,
        "number": _number,
        "boolean": _boolean,
        "array": _array,
        "object": _object,
        # Registries (for runtime to enhance handles)
        "_registries": {
            "agent": _agent_registry,
            "tool": _tool_registry,
            "model": _model_registry,
        },
    }
