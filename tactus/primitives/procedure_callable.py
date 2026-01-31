"""
Lua-callable wrapper for named sub-procedures.

This module provides the ProcedureCallable class that enables direct function
call syntax for named procedures with automatic checkpointing and replay support.
"""

from typing import Any, Optional


class ProcedureCallable:
    """
    Lua-callable wrapper for named sub-procedures.

    Enables direct function call syntax: result = my_proc({input})
    Integrates with checkpoint system for auto-replay.

    Example:
        helper = procedure("helper", {
            input = {x = {type = "number"}},
            output = {y = {type = "number"}}
        }, function()
            return {y = input.x * 2}
        end)

        -- Call it directly:
        result = helper({x = 10})  -- Returns {y = 20}
    """

    def __init__(
        self,
        name: str,
        procedure_function: Any,  # Lua function reference
        input_schema: dict[str, Any],
        output_schema: dict[str, Any],
        state_schema: dict[str, Any],
        execution_context,  # ExecutionContext instance
        lua_sandbox,  # LuaSandbox instance
        is_main: bool = False,  # Whether this is the main entry procedure
    ):
        """
        Initialize a callable procedure wrapper.

        Args:
            name: Procedure name
            procedure_function: Lua function reference to execute
            input_schema: Input validation schema
            output_schema: Output validation schema
            state_schema: State initialization schema
            execution_context: ExecutionContext for checkpointing
            lua_sandbox: LuaSandbox for Lua global management
            is_main: If True, don't checkpoint (main is entry point)
        """
        self.name = name
        self.procedure_function = procedure_function
        self.input_schema = input_schema
        self.output_schema = output_schema
        self.state_schema = state_schema
        self.execution_context = execution_context
        self.lua_sandbox = lua_sandbox
        self.is_main = is_main

    def __call__(self, params: Optional[dict[str, Any]] = None) -> Any:
        """
        Execute the sub-procedure when called from Lua.

        This method is invoked when Lua code calls: result = my_proc({...})

        Args:
            params: Input parameters as a dictionary (converted from Lua table)

        Returns:
            The procedure's result (will be converted to Lua table)

        Raises:
            ValueError: If input validation fails or output is missing required fields
        """
        input_params = params or {}

        # Convert Lua table to dict if needed
        if hasattr(input_params, "items"):
            from tactus.core.dsl_stubs import lua_table_to_dict

            input_params = lua_table_to_dict(input_params)

        # Handle empty list case (lua_table_to_dict converts empty {} to [])
        if isinstance(input_params, list) and len(input_params) == 0:
            input_params = {}

        # Validate input against schema
        self._validate_input(input_params)

        # Wrap execution in checkpoint for automatic replay
        def execute_procedure():
            # Convert Python lists/dicts to Lua tables before setting as input
            def convert_python_value_to_lua(value):
                """Recursively convert Python lists and dicts to Lua tables."""
                if isinstance(value, list):
                    # Convert Python list to Lua table (1-indexed)
                    lua_table = self.lua_sandbox.lua.table()
                    for i, item in enumerate(value, 1):
                        lua_table[i] = convert_python_value_to_lua(item)
                    return lua_table
                elif isinstance(value, dict):
                    # Convert Python dict to Lua table
                    lua_table = self.lua_sandbox.lua.table()
                    for k, v in value.items():
                        lua_table[k] = convert_python_value_to_lua(v)
                    return lua_table
                else:
                    return value

            # Convert params to Lua-compatible format
            lua_input_table = self.lua_sandbox.lua.table()
            for key, value in input_params.items():
                lua_input_table[key] = convert_python_value_to_lua(value)

            # Initialize state defaults WITHOUT replacing the state table
            # (preserving the metatable setup)
            state_default_values = self._initialize_state()
            if state_default_values:
                # Access state via globals and assign - this will trigger the metatable
                state_table = self.lua_sandbox.lua.globals()["state"]
                for key, value in state_default_values.items():
                    state_table[key] = convert_python_value_to_lua(value)

            # Execute the procedure function with input as explicit parameter
            result = self.procedure_function(lua_input_table)

            # Convert Lua table result to Python dict
            # Check for lupa table (not Python dict/list)
            if result and hasattr(result, "items") and not isinstance(result, (dict, list)):
                from tactus.core.dsl_stubs import lua_table_to_dict

                result = lua_table_to_dict(result)

            # Validate output
            self._validate_output(result)

            return result

        # Use existing checkpoint infrastructure for sub-procedures
        # Main procedure is NOT checkpointed (it's the entry point)
        if self.is_main:
            # Main procedure: execute directly without checkpointing
            return execute_procedure()
        else:
            # Sub-procedure: checkpoint for automatic replay
            # Try to capture Lua source location if available
            source_info = None

            # First try to get Lua debug info
            # When called from Lua, we need to find the Lua caller's location
            try:
                # Get debug.getinfo function from Lua globals
                lua_globals = self.lua_sandbox.lua.globals()
                if hasattr(lua_globals, "debug") and hasattr(lua_globals.debug, "getinfo"):
                    # Try different stack levels to find the Lua caller
                    debug_info = None
                    self._write_debug_line(f"DEBUG: Trying debug.getinfo for {self.name}")
                    for stack_level in [1, 2, 3, 4, 5, 6, 7, 8]:
                        try:
                            info = lua_globals.debug.getinfo(stack_level, "Sl")
                            if info:
                                lua_debug_info = (
                                    dict(info.items()) if hasattr(info, "items") else {}
                                )
                                source = lua_debug_info.get("source", "")
                                line = lua_debug_info.get("currentline", -1)
                                self._write_debug_line(
                                    f"DEBUG: Level {stack_level}: source={source}, line={line}"
                                )
                                # Look for a valid source location (not -1, not C function)
                                # Accept [string "<python>"] sources since that's our Lua code
                                if line > 0 and source:
                                    if source.startswith("=[C]"):
                                        continue  # Skip C functions
                                    debug_info = lua_debug_info
                                    self._write_debug_line(
                                        f"DEBUG: Found valid source at level {stack_level}"
                                    )
                                    break
                        except Exception as debug_error:
                            self._write_debug_line(
                                f"DEBUG: Level {stack_level} error: {debug_error}"
                            )
                            continue

                    if debug_info:
                        source_info = {
                            "file": self.execution_context.current_tac_file
                            or debug_info.get("source", "unknown"),
                            "line": debug_info.get("currentline", 0),
                            "function": debug_info.get("name", self.name),
                        }
                        self._write_debug_line(f"DEBUG: Final source_info: {source_info}")
            except Exception as error:
                self._write_debug_line(f"DEBUG: Exception getting Lua debug info: {error}")

            # If we still don't have source_info, use fallback
            if not source_info:
                import inspect

                current_frame = inspect.currentframe()
                if current_frame and current_frame.f_back:
                    caller_frame = current_frame.f_back
                    # Use .tac file if available, otherwise use Python file
                    tac_file = self.execution_context.current_tac_file
                    python_file = caller_frame.f_code.co_filename
                    self._write_debug_line(
                        "DEBUG: Fallback - current_tac_file=%s, python_file=%s"
                        % (tac_file, python_file)
                    )
                    source_info = {
                        "file": tac_file or python_file,
                        "line": 0,  # Line number unknown without Lua debug
                        "function": self.name,
                    }

            return self.execution_context.checkpoint(
                execute_procedure, checkpoint_type="procedure_call", source_info=source_info
            )

    def _validate_input(self, params: dict[str, Any]) -> None:
        """
        Validate input parameters against input schema.

        Args:
            params: Input parameters to validate

        Raises:
            ValueError: If required fields are missing
        """
        missing_inputs = []
        for field_name, field_def in self.input_schema.items():
            if isinstance(field_def, dict) and field_def.get("required", False):
                if field_name not in params:
                    field_type = field_def.get("type", "any")
                    field_desc = field_def.get("description", "")
                    missing_inputs.append(
                        f"  - {field_name} ({field_type}): {field_desc}"
                        if field_desc
                        else f"  - {field_name} ({field_type})"
                    )

        if missing_inputs:
            inputs_list = "\n".join(missing_inputs)
            raise ValueError(
                f"Procedure '{self.name}' requires input parameters that were not provided:\n{inputs_list}\n\n"
                f"To run this procedure, provide the required inputs via the API or use a test specification."
            )

    def _validate_output(self, result: Any) -> None:
        """
        Validate output against output schema.

        Args:
            result: Output to validate

        Raises:
            ValueError: If output is not a dict or missing required fields
        """
        # If no output schema is declared, accept any return value.
        if not self.output_schema:
            return

        # Scalar output schema support:
        #   output = field.string{...}
        if (
            isinstance(self.output_schema, dict)
            and "type" in self.output_schema
            and isinstance(self.output_schema.get("type"), str)
        ):
            expected_type = self.output_schema.get("type")
            if expected_type not in {"string", "number", "boolean", "object", "array"}:
                # Not a scalar schema; treat as normal object schema.
                expected_type = None

        else:
            expected_type = None

        if expected_type is not None:
            is_required = bool(self.output_schema.get("required", False))
            if result is None and not is_required:
                return

            if expected_type == "string" and not isinstance(result, str):
                raise ValueError(f"Procedure '{self.name}' must return string, got {type(result)}")
            if expected_type == "number" and not isinstance(result, (int, float)):
                raise ValueError(f"Procedure '{self.name}' must return number, got {type(result)}")
            if expected_type == "boolean" and not isinstance(result, bool):
                raise ValueError(f"Procedure '{self.name}' must return boolean, got {type(result)}")
            if expected_type == "object" and not isinstance(result, dict):
                raise ValueError(f"Procedure '{self.name}' must return object, got {type(result)}")
            if expected_type == "array" and not isinstance(result, list):
                raise ValueError(f"Procedure '{self.name}' must return array, got {type(result)}")
            return

        if not isinstance(result, dict):
            raise ValueError(f"Procedure '{self.name}' must return dict, got {type(result)}")

        for field_name, field_def in self.output_schema.items():
            if isinstance(field_def, dict) and field_def.get("required", False):
                if field_name not in result:
                    raise ValueError(
                        f"Procedure '{self.name}' missing required output: {field_name}"
                    )

    def _initialize_state(self) -> dict[str, Any]:
        """
        Initialize state with default values from state schema.

        Returns:
            Dictionary with state defaults
        """
        state = {}
        for field_name, field_def in self.state_schema.items():
            if isinstance(field_def, dict) and "default" in field_def:
                state[field_name] = field_def["default"]
        return state

    def _write_debug_line(self, message: str) -> None:
        """Write a debug line to the temporary debug log."""
        with open("/tmp/tactus-debug.log", "a") as debug_file:
            debug_file.write(f"{message}\n")
