from tactus.primitives.tool import ToolPrimitive


def test_tool_record_and_queries():
    tool = ToolPrimitive()
    tool.record_call("search", {"query": "ai"}, {"results": 3})

    assert tool.called("search") is True
    assert tool.get_call_count() == 1
    assert tool.last_result("search") == {"results": 3}
    last_call = tool.last_call("search")
    assert last_call["args"]["query"] == "ai"
