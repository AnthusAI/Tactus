"""
MCP (Model Context Protocol) adapter for Tactus.

Provides integration with MCP servers to load and convert tools for use with Pydantic AI agents.
"""

import logging
import inspect
from types import UnionType
from typing import List, Any, Optional, Dict, get_origin, get_args, Union
from pydantic import create_model, Field
from pydantic_ai import Tool

logger = logging.getLogger(__name__)


def _annotation_includes_str(annotation: Any) -> bool:
    if annotation is str:
        return True
    origin = get_origin(annotation)
    if origin in (Union, UnionType):
        return any(arg is str for arg in get_args(annotation))
    return False


class PydanticAIMCPAdapter:
    """
    Adapter for converting MCP tools to Pydantic AI format.

    Converts MCP tool definitions (with JSON Schema inputSchema) into
    Pydantic AI Tool instances with dynamically generated Pydantic models.
    """

    def __init__(self, mcp_client: Any, tool_primitive: Optional[Any] = None):
        """
        Initialize MCP adapter.

        Args:
            mcp_client: MCP client instance (from fastmcp or similar)
            tool_primitive: Optional ToolPrimitive for recording tool calls
        """
        self.mcp_client = mcp_client
        self.tool_primitive = tool_primitive
        logger.debug("PydanticAIMCPAdapter initialized")

    async def load_tools(self) -> List[Tool]:
        """
        Load tools from MCP server and convert to Pydantic AI Tools.

        Returns:
            List of pydantic_ai.Tool instances

        Note: Assumes MCP client has a method to list tools (e.g., list_tools())
        """
        try:
            # Query MCP server for available tools
            # Common MCP client interface: list_tools() or get_tools()
            if hasattr(self.mcp_client, "list_tools"):
                mcp_tools = await self.mcp_client.list_tools()
            elif hasattr(self.mcp_client, "get_tools"):
                mcp_tools = await self.mcp_client.get_tools()
            else:
                # Try calling as a method that returns tools
                logger.warning(
                    "MCP client doesn't have list_tools() or get_tools(), trying direct call"
                )
                mcp_tools = await self.mcp_client() if callable(self.mcp_client) else []
        except Exception as error:
            logger.error(f"Failed to load tools from MCP server: {error}", exc_info=True)
            return []

        if not mcp_tools:
            logger.warning("No tools found from MCP server")
            return []

        logger.info(f"Found {len(mcp_tools)} tools from MCP server")

        # Convert each MCP tool to Pydantic AI Tool
        pydantic_tools = []
        for mcp_tool in mcp_tools:
            try:
                tool = self._convert_mcp_tool_to_pydantic_ai(mcp_tool)
                if tool:
                    pydantic_tools.append(tool)
            except Exception as error:
                logger.error(
                    f"Failed to convert MCP tool {getattr(mcp_tool, 'name', 'unknown')}: {error}",
                    exc_info=True,
                )

        logger.info(f"Converted {len(pydantic_tools)} tools to Pydantic AI format")
        return pydantic_tools

    def _convert_mcp_tool_to_pydantic_ai(self, mcp_tool: Any) -> Optional[Tool]:
        """
        Convert a single MCP tool to Pydantic AI Tool.

        Args:
            mcp_tool: MCP tool definition (should have name, description, inputSchema)

        Returns:
            pydantic_ai.Tool instance or None if conversion fails
        """
        # Extract tool metadata
        if isinstance(mcp_tool, dict):
            tool_name = mcp_tool.get("name")
            tool_description = mcp_tool.get("description", "")
        else:
            tool_name = getattr(mcp_tool, "name", None)
            tool_description = getattr(mcp_tool, "description", None) or ""

        if not tool_name:
            logger.warning(f"MCP tool missing name: {mcp_tool}")
            return None

        # Extract inputSchema (JSON Schema)
        input_schema = None
        if hasattr(mcp_tool, "inputSchema"):
            input_schema = mcp_tool.inputSchema
        elif isinstance(mcp_tool, dict) and "inputSchema" in mcp_tool:
            input_schema = mcp_tool["inputSchema"]
        elif hasattr(mcp_tool, "parameters"):
            # Some MCP implementations use 'parameters' instead of 'inputSchema'
            input_schema = mcp_tool.parameters

        # Create Pydantic model from JSON Schema
        if input_schema:
            try:
                args_model = self._json_schema_to_pydantic_model(input_schema, tool_name)
            except Exception as error:
                logger.error(
                    f"Failed to create Pydantic model for tool '{tool_name}': {error}",
                    exc_info=True,
                )
                # Fallback: create a simple model that accepts any dict
                args_model = create_model(
                    f"{tool_name}Args", **{"args": (Dict[str, Any], Field(default={}))}
                )
        else:
            # No schema - create empty model
            args_model = create_model(f"{tool_name}Args")

        # Create wrapper function that executes the MCP tool
        async def tool_wrapper(*call_args: Any, **call_kwargs: Any) -> str:
            """
            Wrapper function that executes the MCP tool call.

            Args:
                call_args: Positional arguments from tool invocation
                call_kwargs: Keyword arguments from tool invocation

            Returns:
                Tool result as string
            """
            raw_args: Any = {}
            if call_kwargs:
                raw_args = call_kwargs
                if len(call_args) > 1:
                    raise TypeError(
                        f"Tool '{tool_name}' received unexpected positional arguments: {call_args}"
                    )
            elif len(call_args) == 1:
                raw_args = call_args[0]
            elif len(call_args) == 0:
                raw_args = {}
            else:
                raise TypeError(
                    f"Tool '{tool_name}' received unexpected positional arguments: {call_args}"
                )

            # Normalize and validate arguments through the schema-derived model
            if not isinstance(raw_args, dict):
                if hasattr(raw_args, "model_dump"):
                    raw_args = raw_args.model_dump()
                elif hasattr(raw_args, "dict"):
                    raw_args = raw_args.dict()
                elif hasattr(raw_args, "__iter__") and not isinstance(raw_args, (str, bytes)):
                    try:
                        raw_args = dict(raw_args)
                    except Exception:
                        pass

            if isinstance(raw_args, dict):
                normalized_raw_args = dict(raw_args)
                for field_name, field_info in args_model.model_fields.items():
                    if field_name not in normalized_raw_args:
                        continue
                    value = normalized_raw_args[field_name]
                    if value is None or isinstance(value, str):
                        continue
                    if _annotation_includes_str(field_info.annotation):
                        normalized_raw_args[field_name] = str(value)
                raw_args = normalized_raw_args

            if isinstance(raw_args, args_model):
                validated_args = raw_args
            else:
                try:
                    validated_args = args_model.model_validate(raw_args)
                except Exception:
                    model_fields = getattr(args_model, "model_fields", {})
                    # Backward-compat fallback model: {args: Dict[str, Any]}
                    if len(model_fields) == 1 and "args" in model_fields and isinstance(
                        raw_args, dict
                    ):
                        validated_args = args_model.model_validate({"args": raw_args})
                    else:
                        raise

            # Convert Pydantic model to dict for MCP call
            args_dict = validated_args.model_dump()

            logger.info(f"Executing MCP tool '{tool_name}' with args: {args_dict}")

            try:
                # Call MCP tool - common interface: call_tool(name, args) or tool.execute(args)
                if hasattr(self.mcp_client, "call_tool"):
                    result = await self.mcp_client.call_tool(tool_name, args_dict)
                elif hasattr(self.mcp_client, "call"):
                    result = await self.mcp_client.call(tool_name, args_dict)
                elif hasattr(mcp_tool, "execute"):
                    result = await mcp_tool.execute(args_dict)
                else:
                    # Try calling as a method
                    if callable(mcp_tool):
                        result = await mcp_tool(**args_dict)
                    else:
                        raise ValueError(
                            f"Cannot execute MCP tool '{tool_name}': no callable interface found"
                        )

                # Convert result to string payload expected by downstream Lua/JSON parsing
                result_str = self._result_to_text(result)

                # Record tool call if tool_primitive is available
                if self.tool_primitive:
                    self.tool_primitive.record_call(tool_name, args_dict, result_str)

                logger.debug(f"Tool '{tool_name}' returned: {result_str[:100]}...")
                return result_str

            except Exception as error:
                logger.error(f"MCP tool '{tool_name}' execution failed: {error}", exc_info=True)
                error_msg = f"Error executing tool '{tool_name}': {str(error)}"
                # Still record the failed call
                if self.tool_primitive:
                    self.tool_primitive.record_call(tool_name, args_dict, error_msg)
                raise

        # Expose schema-driven signature so tool callers use explicit keyword args.
        # Keep a backward-compatible "args" annotation for legacy direct calls.
        parameters = []
        for field_name, field_info in args_model.model_fields.items():
            annotation = field_info.annotation if field_info.annotation is not None else Any
            default = (
                inspect.Parameter.empty if field_info.is_required() else field_info.default
            )
            parameters.append(
                inspect.Parameter(
                    field_name,
                    kind=inspect.Parameter.KEYWORD_ONLY,
                    annotation=annotation,
                    default=default,
                )
            )
        tool_wrapper.__signature__ = inspect.Signature(parameters=parameters, return_annotation=str)
        annotations = {"args": args_model, "return": str}
        for field_name, field_info in args_model.model_fields.items():
            if field_name == "args":
                continue
            annotations[field_name] = (
                field_info.annotation if field_info.annotation is not None else Any
            )
        tool_wrapper.__annotations__ = annotations
        tool_wrapper.__name__ = tool_name

        # Create Pydantic AI Tool
        tool = Tool(
            tool_wrapper, name=tool_name, description=tool_description or f"Tool: {tool_name}"
        )

        return tool

    def _result_to_text(self, result: Any) -> str:
        """Normalize MCP tool responses to plain text/JSON strings."""
        # Fast path: already a string
        if isinstance(result, str):
            return result

        # Dict-style responses
        if isinstance(result, dict):
            content = result.get("content")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                text = self._extract_text_from_content_list(content)
                if text is not None:
                    return text
            text = result.get("text")
            if isinstance(text, str):
                return text
            return str(result)

        # Object-style responses (common for MCP SDKs)
        content_attr = getattr(result, "content", None)
        if isinstance(content_attr, str):
            return content_attr
        if isinstance(content_attr, list):
            text = self._extract_text_from_content_list(content_attr)
            if text is not None:
                return text

        text_attr = getattr(result, "text", None)
        if isinstance(text_attr, str):
            return text_attr

        # List responses (possibly MCP content list directly)
        if isinstance(result, list):
            text = self._extract_text_from_content_list(result)
            if text is not None:
                return text
            return str(result)

        return str(result)

    def _extract_text_from_content_list(self, content: List[Any]) -> Optional[str]:
        texts: List[str] = []
        for part in content:
            if isinstance(part, dict):
                text_value = part.get("text")
                if isinstance(text_value, str):
                    texts.append(text_value)
                continue
            text_attr = getattr(part, "text", None)
            if isinstance(text_attr, str):
                texts.append(text_attr)
        if texts:
            return "\n".join(texts)
        return None

    def _json_schema_to_pydantic_model(
        self, schema: Dict[str, Any], base_name: str = "Model"
    ) -> type:
        """
        Convert JSON Schema to a Pydantic model.

        Args:
            schema: JSON Schema dictionary
            base_name: Base name for the generated model

        Returns:
            Pydantic model class
        """
        # Type mapping from JSON Schema to Python types
        type_mapping = {
            "string": str,
            "integer": int,
            "number": float,
            "boolean": bool,
            "array": list,
            "object": dict,
            "null": type(None),
        }

        # Handle schema type
        schema_type = schema.get("type", "object")
        if schema_type != "object":
            # For non-object schemas, create a simple wrapper
            python_type = type_mapping.get(schema_type, Any)
            return create_model(f"{base_name}Args", value=(python_type, Field(...)))

        # Extract properties
        properties = schema.get("properties", {})
        required_fields = schema.get("required", [])

        # Build fields dict for create_model
        fields = {}
        for field_name, field_schema in properties.items():
            field_type_info = field_schema.get("type", "string")
            python_type = type_mapping.get(field_type_info, Any)

            # Check if field is required
            is_required = field_name in required_fields

            # Handle default values
            default_value = field_schema.get("default", ...)
            if not is_required and default_value is ...:
                default_value = None

            # Create Field with description if available
            field_description = field_schema.get("description", "")
            if field_description:
                fields[field_name] = (
                    python_type,
                    Field(default=default_value, description=field_description),
                )
            else:
                fields[field_name] = (python_type, Field(default=default_value))

        # Create the model
        model_name = schema.get("title", f"{base_name}Args")
        return create_model(model_name, **fields)


def convert_mcp_tools_to_pydantic_ai(
    mcp_tools: List[Any], tool_primitive: Optional[Any] = None
) -> List[Tool]:
    """
    Convert MCP tools to Pydantic AI Tool format.

    Args:
        mcp_tools: List of MCP tool objects
        tool_primitive: Optional ToolPrimitive for recording calls

    Returns:
        List of pydantic_ai.Tool objects

    Note: This is a convenience function. For full MCP integration,
    use PydanticAIMCPAdapter with an MCP client.
    """
    # This function is kept for backward compatibility but requires an adapter
    # In practice, use PydanticAIMCPAdapter.load_tools() instead
    logger.warning(
        "convert_mcp_tools_to_pydantic_ai() is deprecated - use PydanticAIMCPAdapter instead"
    )
    return []
