"""
Lua Tools Adapter - Convert DSL-defined Lua functions to Pydantic AI tools.

Supports:
- Individual tool() declarations
- toolset() with type="lua"
- Inline agent tools with lambda functions
"""

import logging
from inspect import Parameter, Signature
from typing import Any, Dict, List, Optional, Callable
from pydantic_ai.toolsets import FunctionToolset
from pydantic import BaseModel, Field, create_model

logger = logging.getLogger(__name__)


class LuaToolsAdapter:
    """Adapter to create Pydantic AI toolsets from Lua function definitions."""

    def __init__(self, tool_primitive: Optional[Any] = None, mock_manager: Optional[Any] = None):
        """
        Initialize adapter.

        Args:
            tool_primitive: Optional ToolPrimitive for call tracking
            mock_manager: Optional MockManager for mock responses
        """
        self.tool_primitive = tool_primitive
        self.mock_manager = mock_manager

    def create_single_tool_toolset(
        self, tool_name: str, tool_spec: Dict[str, Any]
    ) -> FunctionToolset:
        """
        Create a FunctionToolset from a single tool() declaration.

        Used for: tool("name", {...}, function)

        Args:
            tool_name: Name of the tool
            tool_spec: Dict with description, parameters, handler

        Returns:
            FunctionToolset with single tool
        """
        wrapped_fn = self._create_wrapped_function(tool_name, tool_spec)
        logger.info(f"Created single-tool toolset '{tool_name}'")
        return FunctionToolset(tools=[wrapped_fn])

    def create_lua_toolset(
        self, toolset_name: str, toolset_config: Dict[str, Any]
    ) -> FunctionToolset:
        """
        Create a FunctionToolset from toolset() with type="lua".

        Used for: toolset("name", {type="lua", tools={...}})

        Args:
            toolset_name: Name of the toolset
            toolset_config: Dict with type="lua" and tools list

        Returns:
            FunctionToolset with all tools
        """
        tools_list = toolset_config.get("tools", [])
        if not tools_list:
            logger.warning(f"Lua toolset '{toolset_name}' has no tools")
            return FunctionToolset(tools=[])

        wrapped_functions = []
        for tool_spec in tools_list:
            tool_name = tool_spec.get("name")
            if not tool_name:
                logger.error(f"Tool in toolset '{toolset_name}' missing name")
                continue

            wrapped_fn = self._create_wrapped_function(tool_name, tool_spec)
            wrapped_functions.append(wrapped_fn)

        logger.info(f"Created Lua toolset '{toolset_name}' with {len(wrapped_functions)} tools")
        return FunctionToolset(tools=wrapped_functions)

    def create_inline_tools_toolset(
        self, agent_name: str, tools_list: List[Dict[str, Any]]
    ) -> FunctionToolset:
        """
        Create a FunctionToolset from inline agent tools.

        Used for: agent("name", {tools = {{...}}})

        Args:
            agent_name: Name of the agent
            tools_list: List of inline tool specs

        Returns:
            FunctionToolset with inline tools
        """
        wrapped_functions = []
        for tool_spec in tools_list:
            tool_name = tool_spec.get("name")
            if not tool_name:
                logger.error(f"Inline tool for agent '{agent_name}' missing name")
                continue

            # Prefix tool name with agent name for uniqueness
            prefixed_name = f"{agent_name}_{tool_name}"
            wrapped_fn = self._create_wrapped_function(prefixed_name, tool_spec)
            wrapped_functions.append(wrapped_fn)

        logger.info(
            f"Created inline tools for agent '{agent_name}': {len(wrapped_functions)} tools"
        )
        return FunctionToolset(tools=wrapped_functions)

    def create_inline_toolset(
        self, toolset_name: str, tools_list: List[Dict[str, Any]]
    ) -> FunctionToolset:
        """
        Create a FunctionToolset from inline toolset tools.

        Used for: Toolset "name" { tools = {{...}} }

        Args:
            toolset_name: Name of the toolset
            tools_list: List of inline tool specs

        Returns:
            FunctionToolset with inline tools
        """
        wrapped_functions = []
        for tool_spec in tools_list:
            tool_name = tool_spec.get("name")
            if not tool_name:
                logger.error(f"Inline tool for toolset '{toolset_name}' missing name")
                continue

            # Prefix tool name with toolset name for uniqueness
            prefixed_name = f"{toolset_name}_{tool_name}"
            wrapped_fn = self._create_wrapped_function(prefixed_name, tool_spec)
            wrapped_functions.append(wrapped_fn)

        logger.info(f"Created inline toolset '{toolset_name}': {len(wrapped_functions)} tools")
        return FunctionToolset(tools=wrapped_functions)

    def _create_wrapped_function(self, tool_name: str, tool_spec: Dict[str, Any]) -> Callable:
        """
        Create a Python async function that wraps a Lua handler.

        Args:
            tool_name: Tool name for logging/tracking
            tool_spec: Dict with description, parameters, handler

        Returns:
            Async Python function suitable for FunctionToolset
        """
        lua_handler = tool_spec.get("handler")
        if lua_handler is None:
            # Tool/Toolset DSL blocks can specify the handler as an unnamed function value.
            # `lua_table_to_dict()` preserves that as numeric key `1` for mixed tables.
            try:
                candidate = tool_spec.get(1)
            except Exception:
                candidate = None
            if candidate is not None and callable(candidate):
                lua_handler = candidate
        description = tool_spec.get("description", f"Tool: {tool_name}")
        # Only support 'input' field name (new DSL syntax only)
        input_schema = tool_spec.get("input", {})

        # Debug what we received
        logger.debug(f"Tool '{tool_name}' spec keys: {list(tool_spec.keys())}")
        logger.debug(f"Tool '{tool_name}' full spec: {tool_spec}")

        if not lua_handler:
            raise ValueError(f"Tool '{tool_name}' missing handler function")

        # Create Pydantic model for input
        param_model = self._create_parameter_model(tool_name, input_schema)

        # Create async wrapper function
        async def wrapped_tool(**kwargs) -> str:
            """Tool function that calls Lua handler."""
            try:
                # Check for mock response first
                if self.mock_manager:
                    mock_result = self.mock_manager.get_mock_response(tool_name, kwargs)
                    if mock_result is not None:
                        logger.debug(f"Using mock response for '{tool_name}': {mock_result}")
                        # Convert mock result to string to match tool return type
                        result_str = str(mock_result) if mock_result is not None else ""
                        # Track the mock call
                        if self.tool_primitive:
                            self.tool_primitive.record_call(tool_name, kwargs, result_str)
                        self.mock_manager.record_call(tool_name, kwargs, result_str)
                        return result_str

                # Call Lua function directly (Lupa is NOT thread-safe, so we can't use executor)
                # Lua handlers should be fast and don't do I/O, so this won't block significantly

                # Debug: Log what we're passing
                logger.debug(f"Calling Lua tool '{tool_name}' with kwargs: {kwargs}")

                # Tool functions expect parameters as a single 'args' table
                # Pass kwargs directly - Lupa automatically converts Python dicts to Lua tables
                result = lua_handler(kwargs)

                # Convert result to string
                result_str = str(result) if result is not None else ""

                # Record tool call
                if self.tool_primitive:
                    self.tool_primitive.record_call(tool_name, kwargs, result_str)

                # Also track in mock manager for assertions
                if self.mock_manager:
                    self.mock_manager.record_call(tool_name, kwargs, result_str)

                logger.debug(f"Lua tool '{tool_name}' executed successfully")
                return result_str

            except Exception as error:
                error_msg = f"Error executing Lua tool '{tool_name}': {str(error)}"
                logger.error(error_msg, exc_info=True)

                # Record failed call
                if self.tool_primitive:
                    self.tool_primitive.record_call(tool_name, kwargs, error_msg)

                # Re-raise to let agent handle it
                raise RuntimeError(error_msg) from error

        # Build proper signature for Pydantic AI tool discovery
        sig_params = []
        logger.debug(f"Building signature for tool '{tool_name}' with schema: {input_schema}")

        # Lua table iteration order is undefined, so ensure signature is always valid:
        # required params (no defaults) must come before optional params (with defaults).
        required_param_names: list[str] = []
        optional_param_names: list[str] = []
        for param_name in sorted(input_schema.keys()):
            param_spec = input_schema.get(param_name, {}) or {}
            if param_spec.get("required", True):
                required_param_names.append(param_name)
            else:
                optional_param_names.append(param_name)

        for param_name in required_param_names + optional_param_names:
            param_spec = input_schema.get(param_name, {}) or {}
            param_type = self._map_lua_type(param_spec.get("type", "string"))
            required = param_spec.get("required", True)

            if required:
                param = Parameter(
                    param_name, Parameter.POSITIONAL_OR_KEYWORD, annotation=param_type
                )
            else:
                default = param_spec.get("default")
                param = Parameter(
                    param_name,
                    Parameter.POSITIONAL_OR_KEYWORD,
                    default=default,
                    annotation=Optional[param_type],
                )
            sig_params.append(param)

        # Set function metadata for Pydantic AI
        wrapped_tool.__name__ = tool_name
        wrapped_tool.__doc__ = description
        wrapped_tool.__signature__ = Signature(sig_params, return_annotation=str)
        wrapped_tool.__annotations__ = self._build_annotations(param_model)

        return wrapped_tool

    def _create_parameter_model(
        self, tool_name: str, parameters: Dict[str, Dict[str, Any]]
    ) -> type[BaseModel]:
        """
        Create a Pydantic model from Lua parameter specifications.

        Args:
            tool_name: Tool name for model naming
            parameters: Dict of param_name -> {type, description, required}

        Returns:
            Dynamically created Pydantic model class
        """
        if not parameters:
            # No parameters - return empty model
            return create_model(f"{tool_name}Params")

        fields = {}
        for param_name, param_spec in parameters.items():
            param_type_str = param_spec.get("type", "string")
            description = param_spec.get("description", "")
            required = param_spec.get("required", True)

            # Map Lua type strings to Python types
            python_type = self._map_lua_type(param_type_str)

            # Create field
            if required:
                fields[param_name] = (python_type, Field(..., description=description))
            else:
                default = param_spec.get("default")
                fields[param_name] = (
                    Optional[python_type],
                    Field(default=default, description=description),
                )

        return create_model(f"{tool_name}Params", **fields)

    def _map_lua_type(self, lua_type: str) -> type:
        """Map Lua type string to Python type."""
        type_map = {
            "string": str,
            "number": float,
            "integer": int,
            "boolean": bool,
            "table": dict,
            "array": list,
        }
        return type_map.get(lua_type.lower(), str)

    def _build_annotations(self, param_model: type[BaseModel]) -> Dict[str, type]:
        """Build __annotations__ dict from Pydantic model."""
        if not param_model.model_fields:
            return {"return": str}

        annotations = {}
        for field_name, field_info in param_model.model_fields.items():
            annotations[field_name] = field_info.annotation
        annotations["return"] = str
        return annotations
