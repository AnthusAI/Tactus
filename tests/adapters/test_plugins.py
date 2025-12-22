"""
Tests for the local Python plugin loader.
"""

import pytest
from pathlib import Path
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
