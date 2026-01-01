from tactus.primitives.tool import ToolPrimitive, ToolCall


def test_tool_record_and_queries():
    """Test basic tool recording and query functionality."""
    tool = ToolPrimitive()
    tool.record_call("search", {"query": "ai"}, {"results": 3})

    assert tool.called("search") is True
    assert tool.get_call_count() == 1
    assert tool.last_result("search") == {"results": 3}
    last_call = tool.last_call("search")
    assert last_call["args"]["query"] == "ai"


def test_tool_not_called():
    """Test querying a tool that was never called."""
    tool = ToolPrimitive()

    assert tool.called("nonexistent") is False
    assert tool.last_result("nonexistent") is None
    assert tool.last_call("nonexistent") is None
    assert tool.get_call_count("nonexistent") == 0


def test_get_all_calls():
    """Test retrieving complete call history."""
    tool = ToolPrimitive()

    # Record multiple calls
    tool.record_call("search", {"query": "ai"}, {"results": 3})
    tool.record_call("calculate", {"x": 5, "y": 10}, 15)
    tool.record_call("search", {"query": "ml"}, {"results": 5})

    all_calls = tool.get_all_calls()

    assert len(all_calls) == 3
    assert all_calls[0].name == "search"
    assert all_calls[0].args == {"query": "ai"}
    assert all_calls[0].result == {"results": 3}
    assert all_calls[1].name == "calculate"
    assert all_calls[2].name == "search"
    assert all_calls[2].args == {"query": "ml"}


def test_get_call_count_specific_tool():
    """Test counting calls for a specific tool."""
    tool = ToolPrimitive()

    tool.record_call("search", {"query": "ai"}, {"results": 3})
    tool.record_call("calculate", {"x": 5, "y": 10}, 15)
    tool.record_call("search", {"query": "ml"}, {"results": 5})
    tool.record_call("search", {"query": "nlp"}, {"results": 2})

    assert tool.get_call_count("search") == 3
    assert tool.get_call_count("calculate") == 1
    assert tool.get_call_count("nonexistent") == 0


def test_get_call_count_total():
    """Test counting total calls across all tools."""
    tool = ToolPrimitive()

    assert tool.get_call_count() == 0

    tool.record_call("search", {"query": "ai"}, {"results": 3})
    assert tool.get_call_count() == 1

    tool.record_call("calculate", {"x": 5, "y": 10}, 15)
    assert tool.get_call_count() == 2

    tool.record_call("search", {"query": "ml"}, {"results": 5})
    assert tool.get_call_count() == 3


def test_reset():
    """Test resetting tool tracking clears all history."""
    tool = ToolPrimitive()

    # Record some calls
    tool.record_call("search", {"query": "ai"}, {"results": 3})
    tool.record_call("calculate", {"x": 5, "y": 10}, 15)

    assert tool.get_call_count() == 2
    assert tool.called("search") is True

    # Reset and verify everything is cleared
    tool.reset()

    assert tool.get_call_count() == 0
    assert tool.called("search") is False
    assert tool.called("calculate") is False
    assert tool.last_result("search") is None
    assert tool.last_call("search") is None
    assert len(tool.get_all_calls()) == 0


def test_multiple_calls_same_tool():
    """Test that multiple calls to the same tool update last_call correctly."""
    tool = ToolPrimitive()

    # First call
    tool.record_call("search", {"query": "ai"}, {"results": 3})
    assert tool.last_result("search") == {"results": 3}
    assert tool.last_call("search")["args"]["query"] == "ai"

    # Second call - should update last_result/last_call
    tool.record_call("search", {"query": "ml"}, {"results": 5})
    assert tool.last_result("search") == {"results": 5}
    assert tool.last_call("search")["args"]["query"] == "ml"

    # But total calls should be 2
    assert tool.get_call_count("search") == 2

    # And get_all_calls should have both
    all_calls = tool.get_all_calls()
    assert len(all_calls) == 2
    assert all_calls[0].args["query"] == "ai"
    assert all_calls[1].args["query"] == "ml"


def test_multiple_different_tools():
    """Test tracking multiple different tools independently."""
    tool = ToolPrimitive()

    tool.record_call("search", {"query": "ai"}, {"results": 3})
    tool.record_call("calculate", {"x": 5, "y": 10}, 15)
    tool.record_call("summarize", {"text": "..."}, "Summary")

    # Each tool should be tracked independently
    assert tool.called("search") is True
    assert tool.called("calculate") is True
    assert tool.called("summarize") is True
    assert tool.called("nonexistent") is False

    # Last results should be separate
    assert tool.last_result("search") == {"results": 3}
    assert tool.last_result("calculate") == 15
    assert tool.last_result("summarize") == "Summary"

    # Counts should be separate
    assert tool.get_call_count("search") == 1
    assert tool.get_call_count("calculate") == 1
    assert tool.get_call_count("summarize") == 1
    assert tool.get_call_count() == 3


def test_tool_call_dataclass():
    """Test ToolCall dataclass properties."""
    call = ToolCall("search", {"query": "ai"}, {"results": 3})

    assert call.name == "search"
    assert call.args == {"query": "ai"}
    assert call.result == {"results": 3}
    assert call.timestamp is None

    # Test to_dict conversion
    call_dict = call.to_dict()
    assert call_dict["name"] == "search"
    assert call_dict["args"] == {"query": "ai"}
    assert call_dict["result"] == {"results": 3}

    # Test repr
    assert "ToolCall" in repr(call)
    assert "search" in repr(call)


def test_empty_history():
    """Test behavior with empty call history."""
    tool = ToolPrimitive()

    assert tool.get_call_count() == 0
    assert len(tool.get_all_calls()) == 0
    assert tool.called("anything") is False
    assert tool.last_result("anything") is None
    assert tool.last_call("anything") is None
    assert "0 calls" in repr(tool)


def test_tool_with_none_result():
    """Test recording a tool call that returns None."""
    tool = ToolPrimitive()

    tool.record_call("void_function", {"arg": "value"}, None)

    assert tool.called("void_function") is True
    assert tool.last_result("void_function") is None
    assert tool.last_call("void_function")["result"] is None
    assert tool.get_call_count("void_function") == 1


def test_tool_with_complex_args_and_results():
    """Test recording tools with complex nested data structures."""
    tool = ToolPrimitive()

    complex_args = {"nested": {"list": [1, 2, 3], "dict": {"key": "value"}}, "top_level": "string"}

    complex_result = {
        "status": "success",
        "data": [{"id": 1, "name": "item1"}, {"id": 2, "name": "item2"}],
    }

    tool.record_call("complex_tool", complex_args, complex_result)

    assert tool.called("complex_tool") is True
    last_call = tool.last_call("complex_tool")
    assert last_call["args"]["nested"]["list"] == [1, 2, 3]
    assert last_call["result"]["data"][0]["name"] == "item1"
