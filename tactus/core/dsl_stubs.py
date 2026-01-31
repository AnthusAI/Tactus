"""
DSL stub functions for Lua execution.

These functions are injected into the Lua sandbox before executing
.tac files. They populate the registry with declarations.

Current Syntax (assignment-based):
    -- Tools: import from stdlib or define custom
    local done = require("tactus.tools.done")
    multiply = Tool { input = {...}, function(args) ... end }

    -- Agents: assign to variable, tools as variable refs
    greeter = Agent {
        provider = "openai",
        system_prompt = "...",
        tools = {done, multiply}
    }

    -- Procedure: unnamed defaults to "main"
    Procedure {
        output = { result = field.string{required = true} },
        function(input)
            greeter()
            return { result = "done" }
        end
    }

Agent/Tool calls use direct variable access:
    greeter()                       -- Execute agent turn (callable syntax)
    multiply.called()               -- Check if tool was called
    done.last_result()              -- Get last tool result
"""

from typing import Any, Callable

from .registry import RegistryBuilder
from tactus.primitives.handles import AgentHandle, ModelHandle, AgentLookup, ModelLookup
from tactus.stdlib.classify import ClassifyPrimitive


# NEW Builder pattern for field types - moved outside function for import
class FieldDefinition(dict):
    """Special marker class for new field.type{} syntax."""

    pass


def lua_table_to_dict(lua_table: Any) -> Any:
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
        table_keys = list(lua_table.keys())

        # Empty table - return empty list (common for tools = {})
        if not table_keys:
            return []

        # Check if it's an array (all keys are consecutive integers starting from 1)
        if all(isinstance(key, int) for key in table_keys):
            sorted_keys = sorted(table_keys)
            if sorted_keys == list(range(1, len(table_keys) + 1)):
                # It's an array
                return [
                    (
                        lua_table_to_dict(lua_table[key])
                        if hasattr(lua_table[key], "items")
                        else lua_table[key]
                    )
                    for key in sorted_keys
                ]

        # It's a dictionary
        converted_mapping: dict[Any, Any] = {}
        for key, value in lua_table.items():
            # Recursively convert nested tables
            if hasattr(value, "items"):
                converted_mapping[key] = lua_table_to_dict(value)
            else:
                converted_mapping[key] = value
        return converted_mapping

    except (AttributeError, TypeError):
        # Fallback: return as-is
        return lua_table


def _normalize_schema(schema):
    """Convert empty list to empty dict (lua_table_to_dict converts {} to [])."""
    if isinstance(schema, list) and len(schema) == 0:
        return {}
    return schema


def create_dsl_stubs(
    builder: RegistryBuilder,
    tool_primitive: Any = None,
    mock_manager: Any = None,
    runtime_context: dict[str, Any] | None = None,
) -> dict[str, Callable]:
    """
    Create DSL stub functions that populate the registry.

    These functions are injected into the Lua environment before
    executing the .tac file.

    Args:
        builder: RegistryBuilder to register declarations
        tool_primitive: Optional ToolPrimitive for creating callable ToolHandles
        mock_manager: Optional MockManager for checking module mocks
        runtime_context: Optional runtime context for immediate agent creation
                        (includes registry, mock_manager, execution_context, etc.)

    Returns:
        Dict of DSL functions to inject into Lua, including:
        - Lowercase definition functions: agent, tool, procedure, model
        - Uppercase lookup functions: Agent, Tool, Model
    """
    # Registries for handle lookup
    _agent_registry: dict[str, AgentHandle] = {}
    _tool_registry: dict[str, Any] = {}  # ToolHandle instances
    _model_registry: dict[str, ModelHandle] = {}

    # Store runtime context for immediate agent creation
    _runtime_context = runtime_context or {}

    # Global registry for named procedure stubs to find their implementations
    _procedure_registry = {}

    def _process_procedure_config(
        name: str | None, config: Any, procedure_registry: dict[str, Any]
    ):
        """
        Process procedure config and register the procedure.

        This helper extracts the function from config, registers the procedure,
        and returns a stub for later invocation.

        Args:
            name: Procedure name (defaults to "main" if None)
            config: Lua table with procedure config
            procedure_registry: Registry to store procedure stubs

        Returns:
            NamedProcedureStub for the registered procedure
        """
        # Default to "main" if no name provided (for assignment-based syntax)
        if name is None:
            name = "main"
        # Extract the function from the raw Lua table before conversion
        # In Lua tables, unnamed elements are stored with numeric indices (1-based)
        run_function = None

        # Check for function in array part of table (numeric indices)
        if hasattr(config, "__getitem__"):
            # Try to get function from numeric indices (Lua uses 1-based indexing)
            for index in range(1, 10):  # Check first few positions
                try:
                    candidate_item = config[index]
                    if callable(candidate_item):
                        run_function = candidate_item
                        # Remove from table so it doesn't appear in config_dict
                        config[index] = None
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
            else:
                # Ignore extra positional entries that cannot be mapped to config fields.
                config_dict = {}

        # If no function found in array part, check for legacy 'run' field
        if run_function is None:
            run_function = config_dict.pop("run", None)

        if run_function is None:
            raise TypeError(
                f"Procedure '{name}' requires a function. "
                f"Use: Procedure {{ input = {{...}}, function() ... end }}"
            )

        # Extract schemas (normalize empty lists to dicts)
        input_schema = _normalize_schema(config_dict.get("input", {}))
        output_schema = _normalize_schema(config_dict.get("output", {}))
        state_schema = _normalize_schema(config_dict.get("state", {}))

        # Also extract dependencies schema if present
        dependencies_schema = _normalize_schema(config_dict.get("dependencies", {}))

        # Register named procedure (pass dependencies as part of state for now)
        # Future: Add dedicated dependencies field to registry
        if dependencies_schema:
            state_schema["_dependencies"] = dependencies_schema

        builder.register_named_procedure(
            name, run_function, input_schema, output_schema, state_schema
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

        stub = NamedProcedureStub(name, procedure_registry)
        procedure_registry[name] = stub  # Store stub temporarily
        return stub

    def _procedure(name_or_config=None, config=None, run_fn=None):
        """
        Procedure definition supporting multiple syntax variants.

        Unnamed syntax (becomes the main entry point):
            Procedure {
                input = {...},
                output = {...},
                function(input) ... end
            }
            -- This automatically becomes "main" procedure

        Named procedure syntax:
            main = Procedure {
                input = {...},
                output = {...},
                function(input)
                    return {result = input.value * 2}
                end
            }

        Sub-procedure syntax:
            helper = Procedure {
                input = {...},
                output = {...},
                function(input)
                    return {result = input.value * 2}
                end
            }

        Note: Only ONE unnamed Procedure is allowed per file.
        Multiple unnamed Procedures will result in a validation error.

        Args:
            name_or_config: Must be None (assignment-based syntax)
            config: Procedure configuration table
            run_fn: Not used (kept for compatibility)

        Returns:
            ProcedureStub that will be registered when assigned to a variable
        """
        # Check if this is assignment-based syntax: main = Procedure { ... }
        # In this case, name_or_config is the table/config
        if name_or_config is not None and hasattr(name_or_config, "items"):
            # This is: variable = Procedure { ... }
            # We can't know the variable name here, so return a callable stub
            # that will process the config when assigned
            config_table = name_or_config
            return _process_procedure_config(None, config_table, _procedure_registry)

        # First argument must be a string name for curried syntax
        name = name_or_config
        if name is not None and not isinstance(name, str):
            raise TypeError(
                f"Procedure() first argument must be a string name, got {type(name).__name__}"
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
            return _process_procedure_config(name, config, _procedure_registry)

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

    def _specification(*args) -> None:
        """Register BDD specs.

        Supported forms:
          - Specification([[ Gherkin text ]])    (inline Gherkin)
          - Specification("name", { ... })       (structured form; legacy)
          - Specification { from = "path" }      (external file reference)
        """
        if len(args) == 1:
            single_argument = args[0]
            # Check if it's a table with 'from' parameter
            if isinstance(single_argument, dict) or (
                hasattr(single_argument, "keys") and callable(single_argument.keys)
            ):
                config = (
                    lua_table_to_dict(single_argument)
                    if not isinstance(single_argument, dict)
                    else single_argument
                )
                if "from" in config:
                    builder.register_specs_from(config["from"])
                    return
            # Otherwise treat as inline Gherkin text
            builder.register_specifications(single_argument)
            return
        if len(args) >= 2:
            spec_name, scenarios = args[0], args[1]
            builder.register_specification(spec_name, lua_table_to_dict(scenarios))
            return
        raise TypeError("Specification expects gherkin_text, {from='path'}, or (name, scenarios)")

    def _specifications(gherkin_text: str) -> None:
        """Register Gherkin BDD specifications."""
        builder.register_specifications(gherkin_text)

    def _step(step_text: str, lua_function) -> None:
        """Register a custom step definition."""
        builder.register_custom_step(step_text, lua_function)

    def _evaluation(config) -> None:
        """Register evaluation configuration.

        Supported forms:
          - Evaluation({ runs=..., parallel=... })          (single-run config)
          - Evaluation({ dataset=..., evaluators=..., ...}) (alias for Evaluations)
        """
        config_dict = lua_table_to_dict(config or {})
        evaluation_keys = ("dataset", "dataset_file", "evaluators", "thresholds")
        if any(key in config_dict for key in evaluation_keys):
            builder.register_evaluations(config_dict)
            return
        builder.set_evaluation_config(config_dict)

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

    def _first_n(n: int) -> tuple:
        """Filter to keep first N messages."""
        return ("first_n", n)

    def _token_budget(max_tokens: int) -> tuple:
        """Filter by token budget."""
        return ("token_budget", max_tokens)

    def _head_tokens(max_tokens: int) -> tuple:
        """Filter to keep earliest messages within token budget."""
        return ("head_tokens", max_tokens)

    def _tail_tokens(max_tokens: int) -> tuple:
        """Filter to keep latest messages within token budget."""
        return ("tail_tokens", max_tokens)

    def _by_role(role: str) -> tuple:
        """Filter by message role."""
        return ("by_role", role)

    def _system_prefix() -> tuple:
        """Filter to keep leading system messages."""
        return ("system_prefix", None)

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
    def _required(type_name: str, description: str = None) -> dict:  # pragma: no cover
        """Create a required field of given type."""
        result = {"type": type_name, "required": True}
        if description:
            result["description"] = description
        return result

    def _string(default: str = None, description: str = None) -> dict:  # pragma: no cover
        """Create an optional string field."""
        result = {"type": "string", "required": False}
        if default is not None:
            result["default"] = default
        if description:
            result["description"] = description
        return result

    def _number(default: float = None, description: str = None) -> dict:  # pragma: no cover
        """Create an optional number field."""
        result = {"type": "number", "required": False}
        if default is not None:
            result["default"] = default
        if description:
            result["description"] = description
        return result

    def _boolean(default: bool = None, description: str = None) -> dict:  # pragma: no cover
        """Create an optional boolean field."""
        result = {"type": "boolean", "required": False}
        if default is not None:
            result["default"] = default
        if description:
            result["description"] = description
        return result

    def _array(default: list = None, description: str = None) -> dict:  # pragma: no cover
        """Create an optional array field."""
        result = {"type": "array", "required": False}
        if default is not None:
            result["default"] = default if default else []
        if description:
            result["description"] = description
        return result

    def _object(default: dict = None, description: str = None) -> dict:  # pragma: no cover
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
            if isinstance(options, list) and len(options) == 0:
                options = {}

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

    def _evaluator_builder(evaluator_type: str):
        """Create a simple evaluator config builder for Evaluation(s)({ evaluators = {...} })."""

        def build_evaluator(options=None):
            if options is None:
                options = {}
            if hasattr(options, "items"):
                options = lua_table_to_dict(options)
            if not isinstance(options, dict):
                options = {}
            evaluator_config = {"type": evaluator_type}
            evaluator_config.update(options)
            return evaluator_config

        return build_evaluator

    # Evaluation(s)() helper constructors (Pydantic Evals integration).
    # These are configuration builders, not runtime behavior.
    field["equals_expected"] = _evaluator_builder("equals_expected")
    field["min_length"] = _evaluator_builder("min_length")
    field["contains"] = _evaluator_builder("contains")

    # Create lookup functions for uppercase names (Agent, Model)
    # These allow: Agent("greeter")(), Model("classifier")()  (callable syntax)
    _Agent = AgentLookup(_agent_registry)
    _Model = ModelLookup(_model_registry)

    # For Tool lookup, we'll add __call__ to ToolPrimitive
    # Set the tool registry on the primitive so it can do lookups
    if tool_primitive is not None:
        tool_primitive.set_tool_registry(_tool_registry)

    # Create hybrid functions that handle both definition and lookup
    class HybridModel:
        """Callable that handles both Model definition and lookup."""

        def __init__(self, definer, lookup):
            self.definer = definer
            self.lookup = lookup

        def __call__(self, name, config=None):
            try:
                # NEW: Assignment syntax - Model {config} with no name
                # When called as: my_model = Model {type = "http", ...}
                # Lua passes the config table (not a string, not None)
                if not isinstance(name, str) and config is None:
                    # Assignment syntax: generate temp name and register
                    import uuid

                    temporary_name = f"_temp_model_{uuid.uuid4().hex[:8]}"
                    config_dict = lua_table_to_dict(name)
                    builder.register_model(temporary_name, config_dict)

                    handle = ModelHandle(temporary_name)
                    _model_registry[temporary_name] = handle
                    return handle

                # If config is provided, it's old-style definition: Model("name", {config})
                if config is not None:
                    return self.definer(name, config)

                # If called with just a string
                if isinstance(name, str):
                    # Check if the model is already defined (lookup case)
                    try:
                        if self.lookup and name in self.lookup._registry:
                            # This is a lookup: Model("name") where model exists
                            return self.lookup(name)
                    except (TypeError, KeyError):
                        pass
                    # This is the start of a definition: Model "name" {...}
                    # Return the curried function from definer
                    return self.definer(name)

                # Otherwise pass through to definer
                return self.definer(name, config)  # pragma: no cover
            except TypeError as error:
                # Handle unhashable type errors from Lua tables
                if "unhashable type" in str(error):
                    # This is assignment syntax with a Lua table
                    import uuid

                    temporary_name = f"_temp_model_{uuid.uuid4().hex[:8]}"
                    config_dict = lua_table_to_dict(name)
                    builder.register_model(temporary_name, config_dict)

                    handle = ModelHandle(temporary_name)
                    _model_registry[temporary_name] = handle
                    return handle
                raise

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
                def accept_config(config):
                    """Accept config and create structured signature."""
                    config_dict = lua_table_to_dict(config)

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

        # Note: With unified mocking, mocks are handled at Module/Agent level
        # LM configuration still happens normally; mocks intercept at call time

        # Check if this is curried syntax (config is None, return acceptor)
        if config is None:
            # Return a function that accepts config
            def accept_config(config_override=None):
                config_dict = lua_table_to_dict(config_override) if config_override else {}
                return configure_lm(model, **config_dict)

            # Also allow immediate call without config
            # This handles: LM("openai/gpt-4o") with no second arg
            return accept_config

        # Direct call with config: LM("model", {config})
        config_dict = lua_table_to_dict(config)
        return configure_lm(model, **config_dict)

    def _mocks(config):
        """
        Define mock configurations for tools and agents.

        Example usage:
            Mocks {
                -- Tool mocks
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
                },

                -- Agent mocks (specifies what tool calls to simulate)
                my_agent = {
                    tool_calls = {
                        {tool = "search", args = {query = "test"}},
                        {tool = "done", args = {reason = "completed"}}
                    },
                    message = "I found the results."
                }
            }

        Args:
            config: Lua table containing mock definitions
        """
        if config is None:
            return

        config_dict = lua_table_to_dict(config)

        # Register mock configurations with the builder
        for name, mock_config in config_dict.items():
            if not isinstance(mock_config, dict):
                continue

            # Agent mocks can be message-only, tool_calls-only, or both.
            if any(k in mock_config for k in ("tool_calls", "message", "data", "usage")):
                agent_config = {
                    "tool_calls": mock_config.get("tool_calls", []),
                    "message": mock_config.get("message", ""),
                    "data": mock_config.get("data", {}),
                    "usage": mock_config.get("usage", {}),
                    "temporal": mock_config.get("temporal", []),
                }
                builder.register_agent_mock(name, agent_config)
                continue

            # Tool mocks use explicit keys.
            tool_mock_keys = {"returns", "temporal", "conditional", "error"}
            if any(key in mock_config for key in tool_mock_keys):
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
                    for conditional in mock_config["conditional"]:
                        if (
                            isinstance(conditional, dict)
                            and "when" in conditional
                            and "returns" in conditional
                        ):
                            conditionals.append(
                                {
                                    "when": conditional["when"],
                                    "return": conditional["returns"],
                                }
                            )
                    processed_config["conditional_mocks"] = conditionals

                # Error simulation (fallback when no other tool mock key matched)
                else:
                    processed_config["error"] = mock_config["error"]

                # Register the tool mock configuration
                builder.register_mock(name, processed_config)
                continue

            # Otherwise, ignore unknown mock config.
            continue

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
            message_entries = lua_table_to_dict(messages)
            return create_history(message_entries)
        return create_history()

    class TactusMessage:
        """
        First-class Message primitive for conversation history.

        Represents a single message in a conversation with validated role and content.
        """

        VALID_ROLES = {"user", "assistant", "system"}

        def __init__(self, role: str, content: str, **metadata):
            if role not in self.VALID_ROLES:
                raise ValueError(
                    f"Invalid role '{role}'. Must be one of: {', '.join(self.VALID_ROLES)}"
                )
            self.role = role
            self.content = content
            self.metadata = metadata

        def to_dict(self):
            """Convert to dict format for history/DSPy."""
            result = {"role": self.role, "content": self.content}
            if self.metadata:
                result.update(self.metadata)
            return result

        def __repr__(self):
            content_preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
            return f"Message(role='{self.role}', content='{content_preview}')"

    def _message(config):
        """
        Create a Message for use in conversation history.

        Message is a first-class primitive representing a single message
        in a multi-turn conversation. It validates role and provides
        a clean API for building conversation history.

        Valid roles: user, assistant, system

        Example (Lua):
            -- Create messages
            msg = Message {role = "user", content = "Hello"}
            msg = Message {role = "assistant", content = "Hi there!"}
            msg = Message {role = "system", content = "You are helpful"}

            -- Add to history
            history.add(msg)

        Args:
            config: Table with 'role' and 'content' fields

        Returns:
            TactusMessage instance
        """
        config_dict = lua_table_to_dict(config)

        role = config_dict.get("role")
        content = config_dict.get("content")

        if not role:
            raise ValueError("Message requires 'role' field")
        if not content:
            raise ValueError("Message requires 'content' field")

        # Extract any additional metadata
        metadata = {
            key: value for key, value in config_dict.items() if key not in ("role", "content")
        }

        return TactusMessage(role, content, **metadata)

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
            return create_module(
                module_name, config_dict, registry=builder.registry, mock_manager=mock_manager
            )

        # New curried syntax - return a function that accepts config
        def accept_config(config):
            """Accept config and create module."""
            config_dict = lua_table_to_dict(config)
            return create_module(
                module_name, config_dict, registry=builder.registry, mock_manager=mock_manager
            )

        return accept_config

    def _get_current_lm():
        """
        Get the currently configured Language Model.

        Returns:
            The current LM instance or None if not configured
        """
        from tactus.dspy import get_current_lm

        return get_current_lm()

    def _dspy_agent(config=None):
        """
        Create a DSPy Agent.

        Supports curried syntax: DSPyAgent { system_prompt = "...", ... }

        Args:
            config: Optional config dict

        Returns:
            A DSPyAgentHandle instance

        Example (Lua):
            local agent = DSPyAgent {
                system_prompt = "You are a helpful assistant"
            }

            -- Use the agent
            local result = agent:turn({ input = "Hello" })
        """
        from tactus.dspy import create_dspy_agent

        # If config provided directly, create agent
        if config is not None:
            config_dict = lua_table_to_dict(config)
            # Generate a unique name if not provided
            agent_name = config_dict.pop("name", "dspy_agent")
            return create_dspy_agent(
                agent_name, config_dict, registry=builder.registry, mock_manager=mock_manager
            )

        # Curried form - return function that accepts config
        def accept_config(config):
            """Accept config and create DSPy agent."""
            config_dict = lua_table_to_dict(config)
            agent_name = config_dict.pop("name", "dspy_agent")
            return create_dspy_agent(
                agent_name, config_dict, registry=builder.registry, mock_manager=mock_manager
            )

        return accept_config

    # ========================================================================
    # NEW SYNTAX SUPPORT - Phase B
    # ========================================================================

    # Create MCP namespace for accessing MCP server tools
    class McpServerNamespace:
        """Namespace for a specific MCP server's tools."""

        def __init__(self, server_name: str):
            self.server_name = server_name

        def __getattr__(self, tool_name: str):
            """Dynamically create tool handles for MCP tools."""
            from tactus.primitives.tool_handle import ToolHandle

            full_name = f"mcp.{self.server_name}.{tool_name}"

            # Return existing handle if already created
            if full_name in _tool_registry:
                return _tool_registry[full_name]

            # Create a placeholder handler - will be replaced by runtime
            def mcp_placeholder_handler(args):
                raise RuntimeError(
                    f"MCP tool '{full_name}' not connected. "
                    f"Configure MCP server '{self.server_name}' in runtime."
                )

            # Register the tool with MCP source info
            config = {
                "description": f"MCP tool from {self.server_name}",
                "source": full_name,
                "mcp_server": self.server_name,
                "mcp_tool": tool_name,
            }
            builder.register_tool(full_name, config, mcp_placeholder_handler)

            # Create and register handle
            handle = ToolHandle(full_name, mcp_placeholder_handler, tool_primitive)
            _tool_registry[full_name] = handle
            return handle

    class McpNamespace:
        """
        Namespace for MCP server tools.

        Supports syntax like:
            read_file = mcp.filesystem.read_file
            search = mcp.brave_search.search

        The tool handle is created as a placeholder that will be
        connected to the actual MCP server at runtime.
        """

        def __getattr__(self, server_name: str):
            """Return a server namespace for the given MCP server."""
            return McpServerNamespace(server_name)

    _mcp_namespace = McpNamespace()

    def _process_tool_config(tool_name, config):  # pragma: no cover
        """
        Process tool configuration for both curried and direct syntax.

        Args:
            tool_name: Name of the tool
            config: Configuration table

        Returns:
            ToolHandle
        """
        from tactus.primitives.tool_handle import ToolHandle

        # Extract function from config
        handler_function = None
        if hasattr(config, "__getitem__"):
            for index in range(1, 10):
                try:
                    candidate_item = config[index]
                    if callable(candidate_item):
                        handler_function = candidate_item
                        config[index] = None
                        break
                except (KeyError, TypeError, IndexError):
                    break

        # Convert to dict
        config_dict = lua_table_to_dict(config)

        # Clean up None values from function extraction
        if isinstance(config_dict, list):
            config_dict = [x for x in config_dict if x is not None]
            # Ignore extra positional entries that can't be mapped to config fields.
            config_dict = {}

        # Normalize empty schemas (lua {} -> python []) so tools treat empty schemas
        # as empty objects, not arrays.
        if isinstance(config_dict, dict):
            config_dict["input"] = _normalize_schema(config_dict.get("input", {}))
            config_dict["output"] = _normalize_schema(config_dict.get("output", {}))

        # Check for legacy handler field
        if handler_function is None and isinstance(config_dict, dict):
            handler_function = config_dict.pop("handler", None)

        # Tool sources: allow `use = "..."` (or legacy/internal `source = "..."`) in lieu of a handler.
        source = None
        if isinstance(config_dict, dict):
            source = config_dict.pop("use", None)
            if source is not None:
                if "source" in config_dict:
                    raise TypeError(f"Tool '{tool_name}' cannot specify both 'use' and 'source'")
                config_dict["source"] = source
            else:
                source = config_dict.get("source")

        if handler_function is not None and isinstance(source, str) and source.strip():
            raise TypeError(
                f"Tool '{tool_name}' cannot specify both a function and 'use = \"...\"'"
            )

        is_source_tool = (
            handler_function is None and isinstance(source, str) and bool(source.strip())
        )

        if handler_function is None and not is_source_tool:
            raise TypeError(
                f"Tool '{tool_name}' requires either a function or 'use = \"...\"'. "
                'Example: my_tool = Tool { use = "broker.host.ping" }'
            )

        if is_source_tool:
            source_str = source.strip()

            def source_tool_handler(args):
                import asyncio
                import threading

                # Resolve at call time so runtime toolsets are available.
                if tool_primitive is None:
                    raise RuntimeError(
                        f"Tool '{tool_name}' is not available (tool primitive missing)"
                    )

                runtime = getattr(tool_primitive, "_runtime", None)
                if runtime is None:
                    raise RuntimeError(
                        f"Tool '{tool_name}' is not available (runtime not connected)"
                    )

                toolset = runtime.toolset_registry.get(tool_name)
                if toolset is None:
                    raise RuntimeError(
                        f"Tool '{tool_name}' not resolved from source '{source_str}'"
                    )

                tool_function = tool_primitive._extract_tool_function(toolset, tool_name)

                # Support both tool_fn(**kwargs) and tool_fn(args_dict) styles.
                # Prefer kwargs (pydantic-ai Tool functions) then fall back to dict.
                if hasattr(args, "items"):
                    args_dict = lua_table_to_dict(args)
                else:
                    args_dict = args or {}
                if not isinstance(args_dict, dict):
                    raise TypeError(f"Tool '{tool_name}' args must be an object/table")

                if asyncio.iscoroutinefunction(tool_function):

                    def run_coroutine_in_thread(coro):
                        try:
                            asyncio.get_running_loop()
                        except RuntimeError:
                            return asyncio.run(coro)

                        result_container = {"value": None, "exception": None}

                        def run_in_thread():
                            try:
                                result_container["value"] = asyncio.run(coro)
                            except Exception as error:
                                result_container["exception"] = error

                        thread = threading.Thread(target=run_in_thread)
                        thread.start()
                        thread.join()

                        if result_container["exception"] is not None:
                            raise result_container["exception"]
                        return result_container["value"]

                    try:
                        return run_coroutine_in_thread(tool_function(**args_dict))
                    except TypeError:
                        return run_coroutine_in_thread(tool_function(args_dict))

                try:
                    return tool_function(**args_dict)
                except TypeError:
                    return tool_function(args_dict)

            handler_function = source_tool_handler

        # Register tool with provided name
        builder.register_tool(tool_name, config_dict, handler_function)
        handle = ToolHandle(
            tool_name,
            handler_function,
            tool_primitive,
            record_calls=not is_source_tool,
        )

        # Store in registry
        _tool_registry[tool_name] = handle

        return handle

    def _new_tool(name_or_config=None):
        """
        New Tool factory for assignment-based syntax.

        Syntax:
            multiply = Tool {
                description = "Multiply two numbers",
                input = {
                    a = field.number{required = true},
                    b = field.number{required = true}
                },
                function(args)
                    return args.a * args.b
                end
            }

        The name is captured via assignment interception.

        Args:
            name_or_config: Configuration table

        Returns:
            ToolHandle that will be assigned to a variable (or returned directly)
        """
        from tactus.primitives.tool_handle import ToolHandle

        if isinstance(name_or_config, str):
            raise TypeError(
                "Curried Tool syntax is not supported. Use assignment syntax: my_tool = Tool { ... }, "
                'or provide an explicit name in the config: Tool { name = "my_tool", ... }.'
            )

        # Handle direct config syntax: multiply = Tool { ... }
        config = name_or_config
        if config is None:
            raise TypeError("Tool requires a configuration table")

        # Extract function from config
        handler_function = None
        if hasattr(config, "__getitem__"):
            for index in range(1, 10):
                try:
                    candidate_item = config[index]
                    if callable(candidate_item):
                        handler_function = candidate_item
                        config[index] = None
                        break
                except (KeyError, TypeError, IndexError):
                    break

        # Convert to dict
        config_dict = lua_table_to_dict(config)

        # Clean up None values from function extraction
        if isinstance(config_dict, list):
            config_dict = [x for x in config_dict if x is not None]
            # Ignore extra positional entries that can't be mapped to config fields.
            config_dict = {}

        # Normalize empty schemas (lua {} -> python []) so tools treat empty schemas
        # as empty objects, not arrays.
        if isinstance(config_dict, dict):
            config_dict["input"] = _normalize_schema(config_dict.get("input", {}))
            config_dict["output"] = _normalize_schema(config_dict.get("output", {}))

        # Check for legacy handler field
        if handler_function is None and isinstance(config_dict, dict):
            handler_function = config_dict.pop("handler", None)

        # Tool sources: allow `use = "..."` (or legacy/internal `source = "..."`) in lieu of a handler.
        source = None
        if isinstance(config_dict, dict):
            source = config_dict.pop("use", None)
            if source is not None:
                if "source" in config_dict:
                    raise TypeError("Tool cannot specify both 'use' and 'source'")
                config_dict["source"] = source
            else:
                source = config_dict.get("source")

        if handler_function is not None and isinstance(source, str) and source.strip():
            raise TypeError("Tool cannot specify both a function and 'use = \"...\"'")

        is_source_tool = (
            handler_function is None and isinstance(source, str) and bool(source.strip())
        )

        if handler_function is None and not is_source_tool:
            raise TypeError(
                "Tool requires either a function or 'use = \"...\"'. "
                'Example: my_tool = Tool { use = "broker.host.ping" }'
            )

        # Optional explicit tool name (primarily for `return Tool { ... }` cases).
        explicit_name = None
        if isinstance(config_dict, dict):
            explicit_name = config_dict.pop("name", None)
            if explicit_name is not None and not isinstance(explicit_name, str):
                raise TypeError("Tool 'name' must be a string")
            if isinstance(explicit_name, str) and not explicit_name.strip():
                raise TypeError("Tool 'name' cannot be empty")

        # Generate a temporary name - will be replaced when assigned
        import uuid

        temporary_name = (
            explicit_name.strip()
            if isinstance(explicit_name, str)
            else f"_temp_tool_{uuid.uuid4().hex[:8]}"
        )

        if is_source_tool:
            import asyncio
            import threading

            source_str = source.strip()
            handle_reference = {"handle": None}

            def source_tool_handler(args):
                # Resolve at call time so runtime toolsets are available.
                if tool_primitive is None:
                    raise RuntimeError("Tool not available (tool primitive missing)")

                runtime = getattr(tool_primitive, "_runtime", None)
                if runtime is None:
                    raise RuntimeError("Tool not available (runtime not connected)")

                resolved_name = (
                    handle_reference["handle"].name
                    if handle_reference["handle"]
                    else temporary_name
                )
                toolset = runtime.toolset_registry.get(resolved_name)
                if toolset is None:
                    raise RuntimeError(
                        f"Tool '{resolved_name}' not resolved from source '{source_str}'"
                    )

                tool_function = tool_primitive._extract_tool_function(toolset, resolved_name)

                # Support both tool_fn(**kwargs) and tool_fn(args_dict) styles.
                # Prefer kwargs (pydantic-ai Tool functions) then fall back to dict.
                if hasattr(args, "items"):
                    args_dict = lua_table_to_dict(args)
                else:
                    args_dict = args or {}
                if not isinstance(args_dict, dict):
                    raise TypeError("Tool args must be an object/table")

                if asyncio.iscoroutinefunction(tool_function):

                    def run_coroutine_in_thread(coro):
                        try:
                            asyncio.get_running_loop()
                        except RuntimeError:
                            return asyncio.run(coro)

                        result_container = {"value": None, "exception": None}

                        def run_in_thread():
                            try:
                                result_container["value"] = asyncio.run(coro)
                            except Exception as error:
                                result_container["exception"] = error

                        thread = threading.Thread(target=run_in_thread)
                        thread.start()
                        thread.join()

                        if result_container["exception"] is not None:
                            raise result_container["exception"]
                        return result_container["value"]

                    try:
                        return run_coroutine_in_thread(tool_function(**args_dict))
                    except TypeError:
                        return run_coroutine_in_thread(tool_function(args_dict))

                try:
                    return tool_function(**args_dict)
                except TypeError:
                    return tool_function(args_dict)

            handler_function = source_tool_handler

        # Register tool
        builder.register_tool(temporary_name, config_dict, handler_function)
        handle = ToolHandle(
            temporary_name,
            handler_function,
            tool_primitive,
            record_calls=not is_source_tool,
        )

        # Store in registry with temp name
        _tool_registry[temporary_name] = handle

        if is_source_tool:
            handle_reference["handle"] = handle

        return handle

    def _process_agent_config(agent_name, config):
        """
        Process agent configuration for both curried and direct syntax.

        Args:
            agent_name: Name of the agent
            config: Configuration table

        Returns:
            AgentHandle
        """
        config_dict = lua_table_to_dict(config)

        # No alias support: toolsets -> tools is not supported.
        if "toolsets" in config_dict:
            raise ValueError(
                f"Agent '{agent_name}': 'toolsets' is not supported. Use 'tools' for tool/toolset references."
            )

        # inline_tools: inline tool definitions only (list of dicts with "handler")
        if "inline_tools" in config_dict:
            inline_tools = config_dict["inline_tools"]
            if isinstance(inline_tools, (list, tuple)):
                non_dict_items = [t for t in inline_tools if not isinstance(t, dict)]
                if non_dict_items:
                    raise ValueError(
                        f"Agent '{agent_name}': 'inline_tools' must be a list of inline tool definitions."
                    )
            elif inline_tools is not None:
                raise ValueError(
                    f"Agent '{agent_name}': 'inline_tools' must be a list of inline tool definitions."
                )

        # tools: tool/toolset references and toolset expressions (filter dicts)
        if "tools" in config_dict:
            tool_references = config_dict["tools"]
            if isinstance(tool_references, (list, tuple)):
                normalized = []
                for tool_entry in tool_references:
                    if isinstance(tool_entry, dict):
                        if "handler" in tool_entry:
                            raise ValueError(
                                f"Agent '{agent_name}': inline tool definitions must be in 'inline_tools', not 'tools'."
                            )
                        normalized.append(tool_entry)
                        continue
                    if hasattr(tool_entry, "name"):  # ToolHandle or ToolsetHandle
                        normalized.append(tool_entry.name)
                    else:
                        normalized.append(tool_entry)
                config_dict["tools"] = normalized

        # Extract input schema if present
        input_schema = None
        if "input" in config_dict:
            input_config = config_dict["input"]
            if isinstance(input_config, dict):
                input_schema = input_config
                config_dict["input_schema"] = input_schema
                del config_dict["input"]

        # Extract output schema if present
        output_schema = None
        if "output" in config_dict:
            output_config = config_dict["output"]
            if isinstance(output_config, dict):
                output_schema = output_config
                config_dict["output_schema"] = output_schema
                del config_dict["output"]

        # No compatibility aliases: session -> message_history is not supported.
        if "session" in config_dict:
            raise ValueError(
                f"Agent '{agent_name}': 'session' is not supported. Use 'message_history'."
            )

        # Register agent with provided name
        builder.register_agent(agent_name, config_dict, output_schema)

        # Create handle
        handle = AgentHandle(agent_name)

        # If we have runtime context, create the agent primitive immediately
        import logging

        logger = logging.getLogger(__name__)

        logger.debug(
            f"[AGENT_CREATION] Agent '{agent_name}': runtime_context={bool(_runtime_context)}, has_log_handler={('log_handler' in _runtime_context) if _runtime_context else False}"
        )

        if _runtime_context:
            from tactus.dspy.agent import create_dspy_agent

            logger.debug(f"[AGENT_CREATION] Attempting immediate creation for agent '{agent_name}'")

            try:
                # Create the actual agent primitive NOW
                # Note: builder.register_agent adds 'name' to config_dict, but create_dspy_agent
                # expects name as a separate parameter. We need to pass config without 'name'.
                agent_config = {k: v for k, v in config_dict.items() if k != "name"}

                # Agent DSL uses `tools` for tool/toolset references; the DSPy agent config uses
                # `toolsets` for the resolved toolsets list.
                if "tools" in agent_config and "toolsets" not in agent_config:
                    agent_config["toolsets"] = agent_config["tools"]
                    del agent_config["tools"]

                # Pre-process model format: combine provider and model into "provider:model"
                # This matches what _setup_agents does
                if "provider" in agent_config and "model" in agent_config:
                    provider = agent_config["provider"]
                    model_id = agent_config["model"]
                    agent_config["model"] = f"{provider}:{model_id}"

                # Add log_handler from runtime context
                if "log_handler" in _runtime_context:
                    agent_config["log_handler"] = _runtime_context["log_handler"]

                agent_primitive = create_dspy_agent(
                    agent_name,
                    agent_config,
                    registry=builder.registry,
                    mock_manager=_runtime_context.get("mock_manager"),
                )

                # Set tool_primitive for mock tool call recording
                tool_primitive = _runtime_context.get("tool_primitive")
                if tool_primitive:
                    agent_primitive._tool_primitive = tool_primitive

                # Connect handle to primitive immediately
                handle._set_primitive(
                    agent_primitive, execution_context=_runtime_context.get("execution_context")
                )
                logger.debug(
                    f"[AGENT_CREATION] Agent '{agent_name}' created immediately during declaration, has_log_handler={hasattr(agent_primitive, 'log_handler') and agent_primitive.log_handler is not None}"
                )

                # Store primitive in a dict so runtime can access it later
                if "_created_agents" not in _runtime_context:
                    _runtime_context["_created_agents"] = {}
                _runtime_context["_created_agents"][agent_name] = agent_primitive
                logger.debug(
                    f"[AGENT_CREATION] Stored agent '{agent_name}' in _created_agents dict"
                )

            except Exception as error:
                logger.error(
                    f"[AGENT_CREATION] Failed to create agent '{agent_name}' immediately: {error}",
                    exc_info=True,
                )
                # Fall back to two-phase initialization if immediate creation fails

        # Register handle for lookup
        _agent_registry[agent_name] = handle

        return handle

    def _new_agent(name_or_config=None):
        """
        New Agent factory for assignment-based and curried syntax.

        Supports both:
        1. Assignment syntax: greeter = Agent { ... }
        2. Curried syntax: Agent "calculator" { ... }

        New syntax:
            greeter = Agent {
                provider = "openai",
                system_prompt = "...",
                tools = {done, multiply},
            }

        The name is captured via assignment interception.

        Args:
            name_or_config: Either a string name (curried) or configuration table

        Returns:
            AgentHandle that will be assigned to variable, or curried function
        """
        # Handle string argument: either curried declaration or lookup
        if isinstance(name_or_config, str):
            agent_name = name_or_config
            # Check if agent already exists - if so, it's a lookup
            if agent_name in _agent_registry:
                return _agent_registry[agent_name]

            # Otherwise, return curried function for declaration
            def accept_config(config):
                return _process_agent_config(agent_name, config)

            return accept_config

        # Handle direct config syntax: greeter = Agent { ... }
        config = name_or_config
        if config is None:
            raise TypeError("Agent requires a configuration table")

        config_dict = lua_table_to_dict(config)

        # No alias support: toolsets -> tools is not supported.
        if "toolsets" in config_dict:
            raise ValueError("Agent: 'toolsets' is not supported. Use 'tools'.")

        # inline_tools: inline tool definitions only (list of dicts with "handler")
        if "inline_tools" in config_dict:
            inline_tools = config_dict["inline_tools"]
            if isinstance(inline_tools, (list, tuple)):
                non_dict_items = [t for t in inline_tools if not isinstance(t, dict)]
                if non_dict_items:
                    raise ValueError(
                        "Agent: 'inline_tools' must be a list of inline tool definitions."
                    )
            elif inline_tools is not None:
                raise ValueError("Agent: 'inline_tools' must be a list of inline tool definitions.")

        # tools: tool/toolset references and toolset expressions (filter dicts)
        if "tools" in config_dict:
            tool_references = config_dict["tools"]
            if isinstance(tool_references, (list, tuple)):
                normalized = []
                for tool_entry in tool_references:
                    if isinstance(tool_entry, dict):
                        if "handler" in tool_entry:
                            raise ValueError(
                                "Agent: inline tool definitions must be in 'inline_tools', not 'tools'."
                            )
                        normalized.append(tool_entry)
                        continue
                    if hasattr(tool_entry, "name"):  # ToolHandle or ToolsetHandle
                        normalized.append(tool_entry.name)
                    else:
                        normalized.append(tool_entry)
                config_dict["tools"] = normalized

        # Extract input schema if present
        input_schema = None
        if "input" in config_dict:
            input_config = config_dict["input"]
            if isinstance(input_config, dict):
                input_schema = input_config
                config_dict["input_schema"] = input_schema
                del config_dict["input"]

        # Extract output schema if present
        output_schema = None
        if "output" in config_dict:
            output_config = config_dict["output"]
            if isinstance(output_config, dict):
                output_schema = output_config
                config_dict["output_schema"] = output_schema
                del config_dict["output"]

        # No compatibility aliases: session -> message_history is not supported.
        if "session" in config_dict:
            raise ValueError("Agent: 'session' is not supported. Use 'message_history'.")

        # Generate a temporary name - will be replaced when assigned
        import uuid

        temporary_agent_name = f"_temp_agent_{uuid.uuid4().hex[:8]}"

        # Register agent
        builder.register_agent(temporary_agent_name, config_dict, output_schema)

        # Create handle
        handle = AgentHandle(temporary_agent_name)

        # If we have runtime context, create the agent primitive immediately
        import logging

        logger = logging.getLogger(__name__)

        logger.debug(
            f"[AGENT_CREATION] Agent '{temporary_agent_name}': runtime_context={bool(_runtime_context)}, has_log_handler={('log_handler' in _runtime_context) if _runtime_context else False}"
        )

        if _runtime_context:
            from tactus.dspy.agent import create_dspy_agent

            logger.debug(
                f"[AGENT_CREATION] Attempting immediate creation for agent '{temporary_agent_name}'"
            )

            try:
                # Create the actual agent primitive NOW
                # Note: builder.register_agent adds 'name' to config_dict, but create_dspy_agent
                # expects name as a separate parameter. We need to pass config without 'name'.
                agent_config = {k: v for k, v in config_dict.items() if k != "name"}

                # Pre-process model format: combine provider and model into "provider:model"
                # This matches what _setup_agents does
                if "provider" in agent_config and "model" in agent_config:
                    provider = agent_config["provider"]
                    model_id = agent_config["model"]
                    agent_config["model"] = f"{provider}:{model_id}"

                # Add log_handler from runtime context
                if "log_handler" in _runtime_context:
                    agent_config["log_handler"] = _runtime_context["log_handler"]

                logger.debug(
                    f"[AGENT_CREATION] Creating agent immediately: name={temporary_agent_name}, has_log_handler={'log_handler' in agent_config}"
                )
                agent_primitive = create_dspy_agent(
                    temporary_agent_name,
                    agent_config,
                    registry=builder.registry,
                    mock_manager=_runtime_context.get("mock_manager"),
                )

                # Set tool_primitive for mock tool call recording
                tool_primitive = _runtime_context.get("tool_primitive")
                if tool_primitive:
                    agent_primitive._tool_primitive = tool_primitive

                # Connect handle to primitive immediately
                handle._set_primitive(
                    agent_primitive, execution_context=_runtime_context.get("execution_context")
                )
                logger.debug(
                    f"[AGENT_CREATION] Agent '{temporary_agent_name}' created immediately during declaration, has_log_handler={hasattr(agent_primitive, 'log_handler') and agent_primitive.log_handler is not None}"
                )

                # Store primitive in a dict so runtime can access it later
                if "_created_agents" not in _runtime_context:
                    _runtime_context["_created_agents"] = {}
                _runtime_context["_created_agents"][temporary_agent_name] = agent_primitive
                logger.debug(
                    f"[AGENT_CREATION] Stored agent '{temporary_agent_name}' in _created_agents dict"
                )

            except Exception as error:
                import traceback

                logger.error(
                    f"[AGENT_CREATION] Failed to create agent '{temporary_agent_name}' immediately: {error}",
                    exc_info=True,
                )
                logger.debug(f"Full traceback: {traceback.format_exc()}")
                # Fall back to two-phase initialization if immediate creation fails

        # Register handle for lookup
        _agent_registry[temporary_agent_name] = handle

        return handle

    def _new_classify(config=None):
        """
        Classify factory for smart classification with retry logic.

        Syntax:
            -- One-shot classification
            result = Classify {
                classes = {"Yes", "No"},
                prompt = "Did the agent greet the customer?",
                input = transcript
            }

            -- Reusable classifier
            classifier = Classify {
                classes = {"positive", "negative", "neutral"},
                prompt = "What is the sentiment?"
            }
            result = classifier(text)

        Config options:
            - classes: List of valid classification values (required)
            - prompt: Classification instruction (required)
            - input: Optional input for one-shot classification
            - max_retries: Maximum retry attempts (default: 3)
            - temperature: Model temperature (default: 0.3)
            - model: Model to use (optional)
            - confidence_mode: "heuristic" or "none" (default: "heuristic")

        Returns:
            ClassifyHandle if no input (reusable)
            ClassifyResult dict if input provided (one-shot)
        """
        if config is None:
            raise TypeError("Classify requires a configuration table")

        # Create a wrapper function that creates agents using _new_agent.
        #
        # Important: Classify creates internal agents that are not assigned to a Lua global,
        # so they normally keep a random _temp_agent_* name. If the stdlib passes a stable
        # `name` in the agent config, we rename the handle here so it can be mocked via
        # `Mocks { <name> = { ... } }` in BDD specs.
        def agent_factory(agent_config):
            """Factory function to create Agent instances for Classify."""
            desired_name = None
            if isinstance(agent_config, dict):
                desired_name = agent_config.get("name")

            # Use _new_agent to create an agent handle
            handle = _new_agent(agent_config)

            # Apply stable naming for internal agents when requested.
            if desired_name:
                try:
                    binding_callback(desired_name, handle)
                except Exception:
                    # Best-effort: naming is for mocking/traceability; do not break runtime
                    pass
            return handle

        # Create the classify primitive with the agent factory
        classify_primitive = ClassifyPrimitive(
            agent_factory=agent_factory,
            lua_table_from=None,  # Will be handled by result conversion
            registry=builder.registry if hasattr(builder, "registry") else None,
            mock_manager=mock_manager,
        )

        # Call the primitive with the config
        return classify_primitive(lua_table_to_dict(config))

    binding_callback = _make_binding_callback(
        builder, _tool_registry, _agent_registry, _runtime_context
    )

    return {
        # NEW SYNTAX (Phase B+)
        # Note: stdlib tools are accessed via require("tactus.tools.done") etc.
        "mcp": _mcp_namespace,  # Namespace: mcp.filesystem.read_file
        # Core declarations (CamelCase - for definitions AND lookups)
        "Agent": _new_agent,  # NEW syntax - assignment based
        "Model": HybridModel(_model, _Model),
        "Procedure": _procedure,
        "Prompt": _prompt,
        "Toolset": _toolset,
        "Tool": _new_tool,  # NEW syntax - assignment based
        "Classify": _new_classify,  # NEW stdlib: smart classification with retry
        "Hitl": _hitl,
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
        "get_current_lm": _get_current_lm,
        "Signature": _signature,
        "Module": _module,
        "History": _history,
        "Message": _message,
        "DSPyAgent": _dspy_agent,
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
            "first_n": _first_n,
            "token_budget": _token_budget,
            "head_tokens": _head_tokens,
            "tail_tokens": _tail_tokens,
            "by_role": _by_role,
            "system_prefix": _system_prefix,
            "compose": _compose,
        },
        # Built-in matchers
        "contains": _contains,
        "equals": _equals,
        "matches": _matches,
        # New field builder pattern
        "field": field,
        # Note: Old type functions (string, number, etc.) removed to avoid
        # shadowing Lua built-ins. Use field.string{}, field.number{}, etc.
        # Registries (for runtime to enhance handles)
        "_registries": {
            "agent": _agent_registry,
            "tool": _tool_registry,
            "model": _model_registry,
        },
        # Assignment interception callback
        "_tactus_register_binding": binding_callback,
    }


def _make_binding_callback(
    builder: RegistryBuilder, tool_registry: dict, agent_registry: dict, runtime_context: dict
):
    """
    Factory to create the binding callback with closure over builder/registries/runtime_context.

    This callback is called by Lua's __newindex metatable when assignments happen.
    """
    import logging
    from tactus.primitives.tool_handle import ToolHandle

    callback_logger = logging.getLogger(__name__)

    def _tactus_register_binding(name: str, value: Any) -> None:
        """
        Callback for assignment interception in new syntax.

        Called by Lua's __newindex metatable when assignments like:
            multiply = Tool {...}
            greeter = Agent {...}

        For handles with temp names, this renames them to the assigned name
        and re-registers them in the appropriate registry.

        Args:
            name: Variable name being assigned
            value: Value being assigned
        """
        # Check if this is a ToolHandle with a temp name
        if isinstance(value, ToolHandle):
            old_name = value.name
            if old_name.startswith("_temp_tool_"):
                # Rename the tool
                callback_logger.debug(f"Renaming tool '{old_name}' to '{name}'")
                value.name = name

                # Remove old registry entry, add new one
                if old_name in tool_registry:
                    del tool_registry[old_name]
                tool_registry[name] = value

                # Re-register in builder with correct name
                # Tools are stored in builder.registry.lua_tools
                if hasattr(builder, "registry") and old_name in builder.registry.lua_tools:
                    tool_data = builder.registry.lua_tools.pop(old_name)
                    builder.registry.lua_tools[name] = tool_data
                    callback_logger.debug(
                        f"Re-registered tool '{name}' in builder.registry.lua_tools"
                    )
            elif old_name != name:
                raise RuntimeError(
                    f"Tool name mismatch: assigned to '{name}' but tool is named '{old_name}'. "
                    "Remove the Tool config 'name' field or make it match the assigned variable."
                )

        # Check if this is an AgentHandle with a temp name
        if isinstance(value, AgentHandle):
            old_name = value.name
            if old_name.startswith("_temp_agent_"):
                # Rename the agent handle
                callback_logger.debug(f"[AGENT_RENAME] Renaming agent '{old_name}' to '{name}'")
                value.name = name

                # Also rename the underlying primitive if it exists
                if value._primitive is not None:
                    value._primitive.name = name
                    callback_logger.debug(
                        f"[AGENT_RENAME] Updated primitive name: '{old_name}' -> '{name}'"
                    )

                # Remove old registry entry, add new one
                if old_name in agent_registry:
                    del agent_registry[old_name]
                agent_registry[name] = value

                # Re-register in builder with correct name
                # Agents are stored in builder.registry.agents
                if hasattr(builder, "registry") and old_name in builder.registry.agents:
                    agent_data = builder.registry.agents.pop(old_name)
                    builder.registry.agents[name] = agent_data
                    callback_logger.debug(
                        f"[AGENT_RENAME] Re-registered agent '{name}' in builder.registry.agents"
                    )

                # Update _created_agents dict if this agent was immediately created
                if runtime_context and "_created_agents" in runtime_context:
                    if old_name in runtime_context["_created_agents"]:
                        agent_primitive = runtime_context["_created_agents"].pop(old_name)
                        runtime_context["_created_agents"][name] = agent_primitive
                        callback_logger.debug(
                            f"[AGENT_RENAME] Updated _created_agents dict: '{old_name}' -> '{name}'"
                        )

        # Log all assignments for debugging (only at trace level to avoid noise)
        callback_logger.debug(f"Assignment captured: {name} = {type(value).__name__}")

    return _tactus_register_binding
