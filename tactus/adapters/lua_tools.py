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

    def __init__(self, tool_primitive: Optional[Any] = None):
        """
        Initialize adapter.

        Args:
            tool_primitive: Optional ToolPrimitive for call tracking
        """
        self.tool_primitive = tool_primitive

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
        description = tool_spec.get("description", f"Tool: {tool_name}")
        parameters = tool_spec.get("parameters", {})

        if not lua_handler:
            raise ValueError(f"Tool '{tool_name}' missing handler function")

        # Create Pydantic model for parameters
        param_model = self._create_parameter_model(tool_name, parameters)

        # Create async wrapper function
        async def wrapped_tool(**kwargs) -> str:
            """Tool function that calls Lua handler."""
            try:
                # Convert kwargs to Lua table
                # Lupa automatically converts Python dicts to Lua tables
                lua_args = kwargs

                # Call Lua function directly (Lupa is NOT thread-safe, so we can't use executor)
                # Lua handlers should be fast and don't do I/O, so this won't block significantly
                result = lua_handler(lua_args)

                # Convert result to string
                result_str = str(result) if result is not None else ""

                # Record tool call
                if self.tool_primitive:
                    self.tool_primitive.record_call(tool_name, kwargs, result_str)

                logger.debug(f"Lua tool '{tool_name}' executed successfully")
                return result_str

            except Exception as e:
                error_msg = f"Error executing Lua tool '{tool_name}': {str(e)}"
                logger.error(error_msg, exc_info=True)

                # Record failed call
                if self.tool_primitive:
                    self.tool_primitive.record_call(tool_name, kwargs, error_msg)

                # Re-raise to let agent handle it
                raise RuntimeError(error_msg) from e

        # Build proper signature for Pydantic AI tool discovery
        sig_params = []
        for param_name, param_spec in parameters.items():
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
