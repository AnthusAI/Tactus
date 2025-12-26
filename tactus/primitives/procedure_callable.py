"""
Lua-callable wrapper for named sub-procedures.

This module provides the ProcedureCallable class that enables direct function
call syntax for named procedures with automatic checkpointing and replay support.
"""

from typing import Any, Dict, Optional


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
        input_schema: Dict[str, Any],
        output_schema: Dict[str, Any],
        state_schema: Dict[str, Any],
        execution_context,  # ExecutionContext instance
        lua_sandbox,  # LuaSandbox instance
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
        """
        self.name = name
        self.procedure_function = procedure_function
        self.input_schema = input_schema
        self.output_schema = output_schema
        self.state_schema = state_schema
        self.execution_context = execution_context
        self.lua_sandbox = lua_sandbox

    def __call__(self, params: Optional[Dict[str, Any]] = None) -> Any:
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
        params = params or {}

        # Convert Lua table to dict if needed
        if hasattr(params, "items"):
            from tactus.core.dsl_stubs import lua_table_to_dict

            params = lua_table_to_dict(params)

        # Handle empty list case (lua_table_to_dict converts empty {} to [])
        if isinstance(params, list) and len(params) == 0:
            params = {}

        # Validate input against schema
        self._validate_input(params)

        # Wrap execution in checkpoint for automatic replay
        def execute_procedure():
            # Save parent context (for scope isolation)
            try:
                prev_input = self.lua_sandbox.lua.globals()["input"]
            except (KeyError, AttributeError):
                prev_input = None
            try:
                prev_state = self.lua_sandbox.lua.globals()["state"]
            except (KeyError, AttributeError):
                prev_state = None

            try:
                # Set sub-procedure's isolated input/state
                self.lua_sandbox.set_global("input", params)
                self.lua_sandbox.set_global("state", self._initialize_state())

                # Execute the procedure function
                result = self.procedure_function()

                # Convert Lua table result to Python dict
                # Check for lupa table (not Python dict/list)
                if result and hasattr(result, "items") and not isinstance(result, (dict, list)):
                    from tactus.core.dsl_stubs import lua_table_to_dict

                    result = lua_table_to_dict(result)

                # Validate output
                self._validate_output(result)

                return result

            finally:
                # Always restore parent context (even on error)
                if prev_input is not None:
                    self.lua_sandbox.set_global("input", prev_input)
                if prev_state is not None:
                    self.lua_sandbox.set_global("state", prev_state)

        # Use existing checkpoint infrastructure
        # This handles both execution and replay automatically
        return self.execution_context.checkpoint(
            execute_procedure, checkpoint_type="procedure_call"
        )

    def _validate_input(self, params: Dict[str, Any]) -> None:
        """
        Validate input parameters against input schema.

        Args:
            params: Input parameters to validate

        Raises:
            ValueError: If required fields are missing
        """
        for field_name, field_def in self.input_schema.items():
            if isinstance(field_def, dict) and field_def.get("required", False):
                if field_name not in params:
                    raise ValueError(
                        f"Procedure '{self.name}' missing required input: {field_name}"
                    )

    def _validate_output(self, result: Any) -> None:
        """
        Validate output against output schema.

        Args:
            result: Output to validate

        Raises:
            ValueError: If output is not a dict or missing required fields
        """
        if not isinstance(result, dict):
            raise ValueError(f"Procedure '{self.name}' must return dict, got {type(result)}")

        for field_name, field_def in self.output_schema.items():
            if isinstance(field_def, dict) and field_def.get("required", False):
                if field_name not in result:
                    raise ValueError(
                        f"Procedure '{self.name}' missing required output: {field_name}"
                    )

    def _initialize_state(self) -> Dict[str, Any]:
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
