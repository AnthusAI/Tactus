"""Unit tests for LuaToolsAdapter."""

import pytest
from tactus.adapters.lua_tools import LuaToolsAdapter
from tactus.core.lua_sandbox import LuaSandbox


class TestLuaToolsAdapter:
    """Test suite for LuaToolsAdapter."""

    def test_adapter_initialization(self):
        """Test adapter can be initialized."""
        adapter = LuaToolsAdapter()
        assert adapter is not None
        assert adapter.tool_primitive is None

        # With tool_primitive
        class MockToolPrimitive:
            pass

        mock_primitive = MockToolPrimitive()
        adapter = LuaToolsAdapter(tool_primitive=mock_primitive)
        assert adapter.tool_primitive is mock_primitive

    def test_map_lua_type(self):
        """Test Lua type to Python type mapping."""
        adapter = LuaToolsAdapter()

        assert adapter._map_lua_type("string") is str
        assert adapter._map_lua_type("number") is float
        assert adapter._map_lua_type("integer") is int
        assert adapter._map_lua_type("boolean") is bool
        assert adapter._map_lua_type("table") is dict
        assert adapter._map_lua_type("array") is list

        # Case insensitive
        assert adapter._map_lua_type("STRING") is str
        assert adapter._map_lua_type("Number") is float

        # Unknown type defaults to str
        assert adapter._map_lua_type("unknown") is str

    def test_create_parameter_model_empty(self):
        """Test creating parameter model with no parameters."""
        adapter = LuaToolsAdapter()

        model = adapter._create_parameter_model("test_tool", {})
        assert model is not None
        assert len(model.model_fields) == 0

    def test_create_parameter_model_required_params(self):
        """Test creating parameter model with required parameters."""
        adapter = LuaToolsAdapter()

        parameters = {
            "name": {"type": "string", "description": "User name", "required": True},
            "age": {"type": "integer", "description": "User age", "required": True},
        }

        model = adapter._create_parameter_model("test_tool", parameters)
        assert "name" in model.model_fields
        assert "age" in model.model_fields

    def test_create_parameter_model_optional_params(self):
        """Test creating parameter model with optional parameters."""
        adapter = LuaToolsAdapter()

        parameters = {
            "name": {"type": "string", "required": True},
            "nickname": {"type": "string", "required": False, "default": "N/A"},
        }

        model = adapter._create_parameter_model("test_tool", parameters)
        assert "name" in model.model_fields
        assert "nickname" in model.model_fields

    def test_build_annotations(self):
        """Test building function annotations from parameter model."""
        adapter = LuaToolsAdapter()

        parameters = {
            "x": {"type": "number", "required": True},
            "y": {"type": "number", "required": True},
        }

        model = adapter._create_parameter_model("test_tool", parameters)
        annotations = adapter._build_annotations(model)

        assert "x" in annotations
        assert "y" in annotations
        assert "return" in annotations
        assert annotations["return"] is str

    def test_single_tool_toolset_creation(self):
        """Test creating a single-tool toolset."""
        sandbox = LuaSandbox()

        # Create a simple Lua function
        lua_add = sandbox.lua.execute(
            """
            function add(args)
                return args.a + args.b
            end
            return add
        """
        )

        adapter = LuaToolsAdapter()
        tool_spec = {
            "description": "Add two numbers",
            "parameters": {
                "a": {"type": "number", "description": "First number", "required": True},
                "b": {"type": "number", "description": "Second number", "required": True},
            },
            "handler": lua_add,
        }

        toolset = adapter.create_single_tool_toolset("add", tool_spec)
        assert toolset is not None

    def test_lua_toolset_creation(self):
        """Test creating a Lua toolset with multiple tools."""
        sandbox = LuaSandbox()

        lua_add = sandbox.lua.execute(
            """
            function add(args)
                return args.a + args.b
            end
            return add
        """
        )

        lua_multiply = sandbox.lua.execute(
            """
            function multiply(args)
                return args.a * args.b
            end
            return multiply
        """
        )

        adapter = LuaToolsAdapter()
        toolset_config = {
            "type": "lua",
            "tools": [
                {
                    "name": "add",
                    "description": "Add numbers",
                    "parameters": {
                        "a": {"type": "number", "required": True},
                        "b": {"type": "number", "required": True},
                    },
                    "handler": lua_add,
                },
                {
                    "name": "multiply",
                    "description": "Multiply numbers",
                    "parameters": {
                        "a": {"type": "number", "required": True},
                        "b": {"type": "number", "required": True},
                    },
                    "handler": lua_multiply,
                },
            ],
        }

        toolset = adapter.create_lua_toolset("math_tools", toolset_config)
        assert toolset is not None

    def test_lua_toolset_empty_tools(self):
        """Test creating a Lua toolset with no tools."""
        adapter = LuaToolsAdapter()
        toolset_config = {"type": "lua", "tools": []}

        toolset = adapter.create_lua_toolset("empty_toolset", toolset_config)
        assert toolset is not None

    def test_inline_tools_toolset_creation(self):
        """Test creating inline tools toolset."""
        sandbox = LuaSandbox()

        lua_uppercase = sandbox.lua.execute(
            """
            function uppercase(args)
                return string.upper(args.text)
            end
            return uppercase
        """
        )

        adapter = LuaToolsAdapter()
        tools_list = [
            {
                "name": "uppercase",
                "description": "Convert to uppercase",
                "parameters": {"text": {"type": "string", "required": True}},
                "handler": lua_uppercase,
            }
        ]

        toolset = adapter.create_inline_tools_toolset("agent_name", tools_list)
        assert toolset is not None

    def test_create_wrapped_function_missing_handler(self):
        """Test error when handler is missing."""
        adapter = LuaToolsAdapter()

        tool_spec = {
            "description": "Test tool",
            "parameters": {},
            # Missing 'handler' key
        }

        with pytest.raises(ValueError, match="missing handler function"):
            adapter._create_wrapped_function("test_tool", tool_spec)

    @pytest.mark.asyncio
    async def test_wrapped_function_execution(self):
        """Test executing a wrapped Lua function."""
        sandbox = LuaSandbox()

        lua_add = sandbox.lua.execute(
            """
            function add(args)
                return args.a + args.b
            end
            return add
        """
        )

        adapter = LuaToolsAdapter()
        tool_spec = {
            "description": "Add two numbers",
            "parameters": {
                "a": {"type": "number", "required": True},
                "b": {"type": "number", "required": True},
            },
            "handler": lua_add,
        }

        wrapped_fn = adapter._create_wrapped_function("add", tool_spec)
        result = await wrapped_fn(a=5, b=3)

        # Lua returns integers without decimals
        assert result == "8"

    @pytest.mark.asyncio
    async def test_wrapped_function_with_tool_primitive(self):
        """Test that tool calls are recorded in tool primitive."""

        class MockToolPrimitive:
            def __init__(self):
                self.calls = []

            def record_call(self, tool_name, args, result):
                self.calls.append({"tool_name": tool_name, "args": args, "result": result})

        sandbox = LuaSandbox()

        lua_add = sandbox.lua.execute(
            """
            function add(args)
                return args.a + args.b
            end
            return add
        """
        )

        mock_primitive = MockToolPrimitive()
        adapter = LuaToolsAdapter(tool_primitive=mock_primitive)

        tool_spec = {
            "description": "Add two numbers",
            "parameters": {
                "a": {"type": "number", "required": True},
                "b": {"type": "number", "required": True},
            },
            "handler": lua_add,
        }

        wrapped_fn = adapter._create_wrapped_function("add", tool_spec)
        result = await wrapped_fn(a=10, b=20)

        # Lua returns integers without decimals
        assert result == "30"
        assert len(mock_primitive.calls) == 1
        assert mock_primitive.calls[0]["tool_name"] == "add"
        assert mock_primitive.calls[0]["args"] == {"a": 10, "b": 20}
        assert mock_primitive.calls[0]["result"] == "30"

    @pytest.mark.asyncio
    async def test_wrapped_function_error_handling(self):
        """Test error handling in wrapped function."""
        sandbox = LuaSandbox()

        lua_error = sandbox.lua.execute(
            """
            function error_func(args)
                error("Test error")
            end
            return error_func
        """
        )

        adapter = LuaToolsAdapter()
        tool_spec = {
            "description": "Error tool",
            "parameters": {},
            "handler": lua_error,
        }

        wrapped_fn = adapter._create_wrapped_function("error_tool", tool_spec)

        with pytest.raises(RuntimeError, match="Error executing Lua tool"):
            await wrapped_fn()

    @pytest.mark.asyncio
    async def test_wrapped_function_error_recording(self):
        """Test that errors are recorded in tool primitive."""

        class MockToolPrimitive:
            def __init__(self):
                self.calls = []

            def record_call(self, tool_name, args, result):
                self.calls.append({"tool_name": tool_name, "args": args, "result": result})

        sandbox = LuaSandbox()

        lua_error = sandbox.lua.execute(
            """
            function error_func(args)
                error("Test error")
            end
            return error_func
        """
        )

        mock_primitive = MockToolPrimitive()
        adapter = LuaToolsAdapter(tool_primitive=mock_primitive)

        tool_spec = {
            "description": "Error tool",
            "parameters": {},
            "handler": lua_error,
        }

        wrapped_fn = adapter._create_wrapped_function("error_tool", tool_spec)

        with pytest.raises(RuntimeError):
            await wrapped_fn()

        # Error should be recorded
        assert len(mock_primitive.calls) == 1
        assert "Error executing Lua tool" in mock_primitive.calls[0]["result"]

    def test_toolset_with_missing_tool_names(self):
        """Test handling of tools without names in toolset."""
        sandbox = LuaSandbox()

        lua_func = sandbox.lua.execute("function f(args) return 'test' end; return f")

        adapter = LuaToolsAdapter()
        toolset_config = {
            "type": "lua",
            "tools": [
                {
                    # Missing 'name' key
                    "description": "Test tool",
                    "parameters": {},
                    "handler": lua_func,
                }
            ],
        }

        # Should handle missing name gracefully
        toolset = adapter.create_lua_toolset("test_toolset", toolset_config)
        assert toolset is not None
