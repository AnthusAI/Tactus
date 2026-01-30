import pytest

from tactus.adapters.mcp import PydanticAIMCPAdapter


class DummyToolPrimitive:
    def __init__(self):
        self.calls = []

    def record_call(self, name, args, result):
        self.calls.append((name, args, result))


@pytest.mark.asyncio
async def test_adapter_load_tools_with_list_tools():
    class DummyClient:
        async def list_tools(self):
            return [{"name": "echo", "description": "Echo", "inputSchema": {"type": "object"}}]

    adapter = PydanticAIMCPAdapter(DummyClient())

    tools = await adapter.load_tools()

    assert len(tools) == 1
    assert tools[0].name == "echo"


@pytest.mark.asyncio
async def test_adapter_load_tools_skips_missing_name():
    class DummyClient:
        async def list_tools(self):
            return [{"description": "missing name"}]

    adapter = PydanticAIMCPAdapter(DummyClient())

    tools = await adapter.load_tools()

    assert tools == []


@pytest.mark.asyncio
async def test_adapter_load_tools_handles_conversion_error(monkeypatch):
    class DummyClient:
        async def list_tools(self):
            return [{"name": "bad"}]

    adapter = PydanticAIMCPAdapter(DummyClient())

    def raise_convert(_tool):
        raise RuntimeError("boom")

    monkeypatch.setattr(adapter, "_convert_mcp_tool_to_pydantic_ai", raise_convert)

    tools = await adapter.load_tools()

    assert tools == []


@pytest.mark.asyncio
async def test_adapter_tool_wrapper_executes_and_records():
    class DummyClient:
        async def call_tool(self, name, args):
            return {"text": f"{name}:{args.get('query')}"}

    tool_primitive = DummyToolPrimitive()
    adapter = PydanticAIMCPAdapter(DummyClient(), tool_primitive=tool_primitive)

    tool = adapter._convert_mcp_tool_to_pydantic_ai(
        {
            "name": "search",
            "description": "Search",
            "inputSchema": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        }
    )

    args_model = tool.function.__annotations__["args"]
    result = await tool.function(args_model(query="hello"))

    assert result == "search:hello"
    assert tool_primitive.calls[0][0] == "search"


def test_adapter_rejects_tools_without_name(caplog):
    adapter = PydanticAIMCPAdapter(object())

    tool = adapter._convert_mcp_tool_to_pydantic_ai({"description": "missing"})

    assert tool is None


@pytest.mark.asyncio
async def test_adapter_load_tools_with_get_tools():
    class DummyClient:
        async def get_tools(self):
            return [{"name": "ping", "inputSchema": {"type": "object"}}]

    adapter = PydanticAIMCPAdapter(DummyClient())
    tools = await adapter.load_tools()
    assert [tool.name for tool in tools] == ["ping"]


@pytest.mark.asyncio
async def test_adapter_load_tools_with_callable_client(caplog):
    class DummyClient:
        async def __call__(self):
            return []

    adapter = PydanticAIMCPAdapter(DummyClient())
    tools = await adapter.load_tools()
    assert tools == []


@pytest.mark.asyncio
async def test_adapter_load_tools_handles_exception(caplog):
    class DummyClient:
        async def list_tools(self):
            raise RuntimeError("boom")

    adapter = PydanticAIMCPAdapter(DummyClient())
    tools = await adapter.load_tools()
    assert tools == []


def test_adapter_schema_non_object_to_model():
    adapter = PydanticAIMCPAdapter(object())
    model = adapter._json_schema_to_pydantic_model({"type": "string"}, "Thing")
    fields = model.model_fields
    assert "value" in fields


def test_adapter_schema_with_description_field():
    adapter = PydanticAIMCPAdapter(object())
    model = adapter._json_schema_to_pydantic_model(
        {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Search"}},
        },
        "Thing",
    )
    assert model.model_fields["query"].description == "Search"


def test_adapter_schema_error_falls_back_to_args_model(monkeypatch):
    adapter = PydanticAIMCPAdapter(object())

    def raise_schema(_schema, _base_name):
        raise RuntimeError("boom")

    monkeypatch.setattr(adapter, "_json_schema_to_pydantic_model", raise_schema)

    tool = adapter._convert_mcp_tool_to_pydantic_ai(
        {"name": "fallback", "inputSchema": {"type": "object"}}
    )
    args_model = tool.function.__annotations__["args"]

    assert "args" in args_model.model_fields


@pytest.mark.asyncio
async def test_adapter_tool_wrapper_handles_execute_and_records():
    class DummyTool:
        name = "exec"
        description = "Exec"
        parameters = {
            "type": "object",
            "properties": {"value": {"type": "string"}},
        }

        async def execute(self, args):
            return ["ok", args.get("value")]

    tool_primitive = DummyToolPrimitive()
    adapter = PydanticAIMCPAdapter(object(), tool_primitive=tool_primitive)

    tool = adapter._convert_mcp_tool_to_pydantic_ai(DummyTool())
    args_model = tool.function.__annotations__["args"]
    result = await tool.function(args_model(value="v"))

    assert result == "['ok', 'v']"
    assert tool_primitive.calls[0][0] == "exec"


@pytest.mark.asyncio
async def test_adapter_tool_wrapper_handles_callable_tool():
    class DummyTool:
        name = "callable"
        inputSchema = {"type": "object", "properties": {"x": {"type": "string"}}}

        async def __call__(self, **kwargs):
            return {"content": f"ok:{kwargs.get('x')}"}

    adapter = PydanticAIMCPAdapter(object())
    tool = adapter._convert_mcp_tool_to_pydantic_ai(DummyTool())
    args_model = tool.function.__annotations__["args"]
    result = await tool.function(args_model(x="1"))

    assert result == "ok:1"


@pytest.mark.asyncio
async def test_adapter_tool_wrapper_handles_call_method_and_scalar_result():
    class DummyClient:
        async def call(self, name, args):
            return 123

    adapter = PydanticAIMCPAdapter(DummyClient())
    tool = adapter._convert_mcp_tool_to_pydantic_ai(
        {"name": "call", "inputSchema": {"type": "object"}}
    )
    args_model = tool.function.__annotations__["args"]
    result = await tool.function(args_model())

    assert result == "123"


@pytest.mark.asyncio
async def test_adapter_tool_wrapper_handles_missing_schema():
    class DummyClient:
        async def call_tool(self, name, args):
            return "ok"

    adapter = PydanticAIMCPAdapter(DummyClient())
    tool = adapter._convert_mcp_tool_to_pydantic_ai({"name": "noop"})
    args_model = tool.function.__annotations__["args"]
    result = await tool.function(args_model())

    assert result == "ok"


@pytest.mark.asyncio
async def test_adapter_tool_wrapper_raises_when_no_callable():
    class DummyTool:
        name = "bad"
        inputSchema = {"type": "object"}

    adapter = PydanticAIMCPAdapter(object())
    tool = adapter._convert_mcp_tool_to_pydantic_ai(DummyTool())
    args_model = tool.function.__annotations__["args"]

    with pytest.raises(ValueError, match="Cannot execute MCP tool"):
        await tool.function(args_model())


@pytest.mark.asyncio
async def test_adapter_tool_wrapper_records_failure():
    class DummyClient:
        async def call_tool(self, name, args):
            raise RuntimeError("boom")

    tool_primitive = DummyToolPrimitive()
    adapter = PydanticAIMCPAdapter(DummyClient(), tool_primitive=tool_primitive)

    tool = adapter._convert_mcp_tool_to_pydantic_ai(
        {"name": "fail", "inputSchema": {"type": "object"}}
    )
    args_model = tool.function.__annotations__["args"]

    with pytest.raises(RuntimeError):
        await tool.function(args_model())

    assert tool_primitive.calls[0][0] == "fail"
    assert "Error executing tool" in tool_primitive.calls[0][2]


@pytest.mark.asyncio
async def test_adapter_tool_wrapper_uses_dict_args():
    class DummyClient:
        async def call_tool(self, name, args):
            return {"text": "ok"}

    class Args:
        def dict(self):
            return {"x": "1"}

    adapter = PydanticAIMCPAdapter(DummyClient())
    tool = adapter._convert_mcp_tool_to_pydantic_ai(
        {"name": "dict", "inputSchema": {"type": "object"}}
    )
    result = await tool.function(Args())

    assert result == "ok"


@pytest.mark.asyncio
async def test_adapter_tool_wrapper_uses_iterable_args():
    class DummyClient:
        async def call_tool(self, name, args):
            return {"text": "ok"}

    class Args:
        def __iter__(self):
            return iter([("x", "1")])

        @property
        def __dict__(self):
            return {"x": "1"}

    adapter = PydanticAIMCPAdapter(DummyClient())
    tool = adapter._convert_mcp_tool_to_pydantic_ai(
        {"name": "iter", "inputSchema": {"type": "object"}}
    )
    result = await tool.function(Args())

    assert result == "ok"


def test_deprecated_convert_function_returns_empty(caplog):
    from tactus.adapters.mcp import convert_mcp_tools_to_pydantic_ai

    assert convert_mcp_tools_to_pydantic_ai([]) == []
