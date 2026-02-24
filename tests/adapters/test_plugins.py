"""
Tests for the local Python plugin loader.
"""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
from tactus.adapters.plugins import PluginLoader


@pytest.fixture
def plugin_loader():
    """Create a plugin loader instance."""
    return PluginLoader()


@pytest.fixture
def example_tools_dir():
    """Path to the examples/tools directory."""
    return str(Path(__file__).parent.parent.parent / "examples" / "tools")


def test_plugin_loader_initialization(plugin_loader):
    """Test that plugin loader initializes correctly."""
    assert plugin_loader is not None
    assert plugin_loader.loaded_modules == {}


def test_load_from_nonexistent_path(plugin_loader):
    """Test loading from a path that doesn't exist."""
    tools = plugin_loader.load_from_paths(["/nonexistent/path"])
    assert tools == []


def test_load_from_example_tools(plugin_loader, example_tools_dir):
    """Test loading tools from examples/tools directory."""
    tools = plugin_loader.load_from_paths([example_tools_dir])

    # Should load multiple tools
    assert len(tools) > 0

    # Check that tools have names
    tool_names = [tool.name for tool in tools]
    assert "web_search" in tool_names
    assert "calculate_mortgage" in tool_names
    assert "analyze_numbers" in tool_names


def test_load_specific_file(plugin_loader, example_tools_dir):
    """Test loading tools from a specific file."""
    file_path = str(Path(example_tools_dir) / "calculations.py")
    tools = plugin_loader.load_from_paths([file_path])

    # Should load tools from calculations.py
    assert len(tools) > 0

    tool_names = [tool.name for tool in tools]
    assert "calculate_mortgage" in tool_names
    assert "compound_interest" in tool_names
    assert "tip_calculator" in tool_names

    # Should NOT load tools from other files
    assert "web_search" not in tool_names
    assert "analyze_numbers" not in tool_names


def test_tool_has_description(plugin_loader, example_tools_dir):
    """Test that loaded tools have descriptions from docstrings."""
    tools = plugin_loader.load_from_paths([example_tools_dir])

    # Find a specific tool
    mortgage_tool = next((t for t in tools if t.name == "calculate_mortgage"), None)
    assert mortgage_tool is not None

    # Check that description comes from docstring
    assert "mortgage" in mortgage_tool.description.lower()


def test_tool_execution(plugin_loader, example_tools_dir):
    """Test that loaded tools can be executed."""
    tools = plugin_loader.load_from_paths([example_tools_dir])

    # Find the tip_calculator tool
    tip_tool = next((t for t in tools if t.name == "tip_calculator"), None)
    assert tip_tool is not None

    # Execute the tool (it's wrapped, so we need to call the function)
    # Note: The actual execution would be done by Pydantic AI in real usage
    # Here we're just verifying the tool was loaded correctly
    assert callable(tip_tool.function)


def test_private_functions_not_loaded(plugin_loader, tmp_path):
    """Test that private functions (starting with _) are not loaded."""
    # Create a test file with public and private functions
    test_file = tmp_path / "test_tools.py"
    test_file.write_text(
        """
def public_tool(x: int) -> int:
    '''A public tool.'''
    return x * 2

def _private_tool(x: int) -> int:
    '''A private tool.'''
    return x * 3
"""
    )

    tools = plugin_loader.load_from_paths([str(test_file)])

    # Should only load public_tool
    assert len(tools) == 1
    assert tools[0].name == "public_tool"


def test_multiple_paths(plugin_loader, example_tools_dir, tmp_path):
    """Test loading tools from multiple paths."""
    # Create an additional test file
    test_file = tmp_path / "extra_tools.py"
    test_file.write_text(
        """
def extra_tool(message: str) -> str:
    '''An extra tool.'''
    return f"Extra: {message}"
"""
    )

    tools = plugin_loader.load_from_paths([example_tools_dir, str(test_file)])

    # Should load tools from both locations
    tool_names = [tool.name for tool in tools]
    assert "web_search" in tool_names  # From examples/tools
    assert "extra_tool" in tool_names  # From test file


def test_invalid_python_file(plugin_loader, tmp_path):
    """Test handling of invalid Python files."""
    # Create a file with syntax errors
    bad_file = tmp_path / "bad_tools.py"
    bad_file.write_text("def broken(: invalid syntax")

    # Should handle gracefully and return empty list
    tools = plugin_loader.load_from_paths([str(bad_file)])
    assert tools == []


def test_non_python_file_skipped(plugin_loader, tmp_path):
    """Test that non-Python files are skipped."""
    # Create a non-Python file
    text_file = tmp_path / "not_python.txt"
    text_file.write_text("This is not Python code")

    tools = plugin_loader.load_from_paths([str(text_file)])
    assert tools == []


def test_create_toolset_empty_returns_no_tools(tmp_path):
    loader = PluginLoader()
    toolset = loader.create_toolset([str(tmp_path / "missing")])
    assert len(toolset.tools) == 0


def test_create_toolset_with_functions(tmp_path):
    loader = PluginLoader()
    tool_file = tmp_path / "tools.py"
    tool_file.write_text(
        """
def greet(name: str) -> str:
    '''Greets by name.'''
    return f"hi {name}"
"""
    )
    toolset = loader.create_toolset([str(tool_file)])
    assert len(toolset.tools) == 1


def test_load_all_functions_skips_private_module(tmp_path):
    loader = PluginLoader()
    private_file = tmp_path / "_private.py"
    private_file.write_text(
        """
def public_tool(x: int) -> int:
    return x
"""
    )

    functions = loader._load_all_functions([str(tmp_path)])
    assert functions == []


def test_load_from_paths_handles_unknown_path_type(monkeypatch, tmp_path):
    loader = PluginLoader()
    path = tmp_path / "weird"

    monkeypatch.setattr(Path, "exists", lambda _self: True)
    monkeypatch.setattr(Path, "is_file", lambda _self: False)
    monkeypatch.setattr(Path, "is_dir", lambda _self: False)

    tools = loader.load_from_paths([str(path)])
    assert tools == []


def test_load_all_functions_handles_unknown_path_type(monkeypatch, tmp_path):
    loader = PluginLoader()
    path = tmp_path / "weird"

    monkeypatch.setattr(Path, "exists", lambda _self: True)
    monkeypatch.setattr(Path, "is_file", lambda _self: False)
    monkeypatch.setattr(Path, "is_dir", lambda _self: False)

    functions = loader._load_all_functions([str(path)])
    assert functions == []


def test_load_all_functions_skips_non_python_file(tmp_path):
    loader = PluginLoader()
    text_file = tmp_path / "notes.txt"
    text_file.write_text("nope")
    functions = loader._load_all_functions([str(text_file)])
    assert functions == []


def test_load_functions_from_directory(tmp_path):
    loader = PluginLoader()
    tool_file = tmp_path / "tools.py"
    tool_file.write_text(
        """
def greet(name: str) -> str:
    return f"hi {name}"
"""
    )
    functions = loader._load_functions_from_directory(tmp_path)
    assert any(func.__name__ == "greet" for func in functions)


def test_load_functions_from_file_handles_missing_spec(monkeypatch, tmp_path):
    loader = PluginLoader()
    tool_file = tmp_path / "tools.py"
    tool_file.write_text("def greet():\n    return 'hi'\n")

    monkeypatch.setattr(
        importlib.util,
        "spec_from_file_location",
        lambda *_args, **_kwargs: SimpleNamespace(loader=None),
    )

    functions = loader._load_functions_from_file(tool_file)
    assert functions == []


def test_load_functions_from_file_handles_exec_error(tmp_path):
    loader = PluginLoader()
    bad_file = tmp_path / "bad.py"
    bad_file.write_text("def broken(: invalid syntax")

    functions = loader._load_functions_from_file(bad_file)
    assert functions == []


@pytest.mark.asyncio
async def test_trace_callback_records_success():
    class DummyToolPrimitive:
        def __init__(self):
            self.calls = []

        def record_call(self, name, args, result):
            self.calls.append((name, args, result))

    loader = PluginLoader(tool_primitive=DummyToolPrimitive())
    callback = loader._create_trace_callback("tools")

    async def next_call(name, args):
        return {"ok": True, "args": args}

    result = await callback(None, next_call, "tool", {"x": 1})
    assert result["ok"] is True
    assert loader.tool_primitive.calls[0][0] == "tool"


@pytest.mark.asyncio
async def test_trace_callback_records_failure():
    class DummyToolPrimitive:
        def __init__(self):
            self.calls = []

        def record_call(self, name, args, result):
            self.calls.append((name, args, result))

    loader = PluginLoader(tool_primitive=DummyToolPrimitive())
    callback = loader._create_trace_callback("tools")

    async def next_call(_name, _args):
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        await callback(None, next_call, "tool", {"x": 1})
    assert "Error" in loader.tool_primitive.calls[0][2]


@pytest.mark.asyncio
async def test_trace_callback_without_tool_primitive():
    loader = PluginLoader()
    callback = loader._create_trace_callback("tools")

    async def next_call(name, args):
        return {"ok": True}

    result = await callback(None, next_call, "tool", {"x": 1})
    assert result["ok"] is True


@pytest.mark.asyncio
async def test_trace_callback_without_tool_primitive_failure():
    loader = PluginLoader()
    callback = loader._create_trace_callback("tools")

    async def next_call(_name, _args):
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        await callback(None, next_call, "tool", {"x": 1})


def test_load_tools_from_file_skips_failed_tool_creation(monkeypatch, tmp_path):
    loader = PluginLoader()
    tool_file = tmp_path / "tools.py"
    tool_file.write_text(
        """
def greet(name: str) -> str:
    return f"hi {name}"
"""
    )

    monkeypatch.setattr(loader, "_create_tool_from_function", lambda *_args, **_kwargs: None)

    tools = loader._load_tools_from_file(tool_file)
    assert tools == []


def test_load_tools_from_directory_skips_private(tmp_path):
    loader = PluginLoader()
    private_file = tmp_path / "_private.py"
    private_file.write_text("def hidden():\n    return 'x'\n")

    tools = loader._load_tools_from_directory(tmp_path)
    assert tools == []


def test_load_tools_from_file_handles_missing_spec(monkeypatch, tmp_path):
    loader = PluginLoader()
    tool_file = tmp_path / "tools.py"
    tool_file.write_text("def greet():\n    return 'hi'\n")

    monkeypatch.setattr(
        importlib.util,
        "spec_from_file_location",
        lambda *_args, **_kwargs: SimpleNamespace(loader=None),
    )

    tools = loader._load_tools_from_file(tool_file)
    assert tools == []


def test_is_valid_tool_function_rejects_imported():
    loader = PluginLoader()

    def local():
        return "ok"

    module = SimpleNamespace(__name__="module")
    local.__module__ = "other"

    assert loader._is_valid_tool_function("local", local, module) is False


def test_create_tool_from_function_sync_and_error(tmp_path):
    class DummyToolPrimitive:
        def __init__(self):
            self.calls = []

        def record_call(self, name, args, result):
            self.calls.append((name, args, result))

    loader = PluginLoader(tool_primitive=DummyToolPrimitive())

    def greet(name: str) -> str:
        return f"hi {name}"

    tool = loader._create_tool_from_function(greet, "greet")
    assert tool.function(name="sam") == "hi sam"
    assert loader.tool_primitive.calls[0][0] == "greet"

    def boom():
        raise RuntimeError("fail")

    tool = loader._create_tool_from_function(boom, "boom")
    with pytest.raises(RuntimeError):
        tool.function()
    assert "Error executing tool" in loader.tool_primitive.calls[-1][2]


@pytest.mark.asyncio
async def test_create_tool_from_function_async_and_error():
    class DummyToolPrimitive:
        def __init__(self):
            self.calls = []

        def record_call(self, name, args, result):
            self.calls.append((name, args, result))

    loader = PluginLoader(tool_primitive=DummyToolPrimitive())

    async def greet(name: str) -> str:
        return f"hi {name}"

    tool = loader._create_tool_from_function(greet, "greet")
    result = await tool.function(name="sam")
    assert result == "hi sam"

    async def boom():
        raise RuntimeError("fail")

    tool = loader._create_tool_from_function(boom, "boom")
    with pytest.raises(RuntimeError):
        await tool.function()
    assert "Error executing tool" in loader.tool_primitive.calls[-1][2]


def test_create_tool_from_function_sync_without_tool_primitive():
    loader = PluginLoader()

    def greet(name: str) -> str:
        return f"hi {name}"

    tool = loader._create_tool_from_function(greet, "greet")
    assert tool.function(name="sam") == "hi sam"


def test_create_tool_from_function_sync_error_without_tool_primitive():
    loader = PluginLoader()

    def boom():
        raise RuntimeError("fail")

    tool = loader._create_tool_from_function(boom, "boom")
    with pytest.raises(RuntimeError):
        tool.function()


@pytest.mark.asyncio
async def test_create_tool_from_function_async_without_tool_primitive():
    loader = PluginLoader()

    async def greet(name: str) -> str:
        return f"hi {name}"

    tool = loader._create_tool_from_function(greet, "greet")
    result = await tool.function(name="sam")
    assert result == "hi sam"


@pytest.mark.asyncio
async def test_create_tool_from_function_async_error_without_tool_primitive():
    loader = PluginLoader()

    async def boom():
        raise RuntimeError("fail")

    tool = loader._create_tool_from_function(boom, "boom")
    with pytest.raises(RuntimeError):
        await tool.function()


def test_create_tool_from_function_handles_signature_error(monkeypatch):
    loader = PluginLoader()

    def greet():
        return "hi"

    monkeypatch.setattr("inspect.signature", lambda _func: (_ for _ in ()).throw(ValueError()))

    tool = loader._create_tool_from_function(greet, "greet")
    assert tool is None
