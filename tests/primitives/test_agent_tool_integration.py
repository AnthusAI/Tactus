"""
Agent-Tool Integration Tests

Tests for how AgentPrimitive integrates with tools (both local and MCP).
"""

from pydantic_ai import Tool
from tactus.primitives.agent import AgentPrimitive
from tactus.primitives.state import StatePrimitive
from tactus.primitives.control import IterationsPrimitive


def create_test_agent(tools=None, **kwargs):
    """Helper to create a test agent with minimal required parameters."""
    defaults = {
        "name": "test_agent",
        "system_prompt_template": "Test agent",
        "initial_message": "Start",
        "model": "test",
        "tools": tools or [],
        "tool_primitive": kwargs.get("tool_primitive"),
        "stop_primitive": kwargs.get("stop_primitive"),
        "iterations_primitive": IterationsPrimitive(),
        "state_primitive": StatePrimitive(),
        "context": {},
    }
    defaults.update(kwargs)
    return AgentPrimitive(**defaults)


def test_agent_initialization_with_tools():
    """Test that an agent can be initialized with tools."""

    # Create a simple tool function
    def calculate(x: int, y: int) -> int:
        """Add two numbers."""
        return x + y

    # Wrap in Tool object
    calc_tool = Tool(calculate, name="calculate")

    # Create agent with tool
    agent = create_test_agent(tools=[calc_tool])

    # Agent should have exactly the tools provided (no auto-injection)
    assert len(agent.all_tools) == 1
    tool_names = [t.name for t in agent.all_tools]
    assert "calculate" in tool_names


def test_agent_initialization_without_tools():
    """Test that an agent can be initialized without tools."""
    agent = create_test_agent(tools=None)

    # Agent should have no tools
    assert len(agent.all_tools) == 0


def test_agent_tool_filtering_by_name():
    """Test filtering agent tools by name."""

    def tool_a(x: int) -> int:
        """Tool A."""
        return x * 2

    def tool_b(x: int) -> int:
        """Tool B."""
        return x * 3

    tool_a_wrapped = Tool(tool_a, name="tool_a")
    tool_b_wrapped = Tool(tool_b, name="tool_b")

    agent = create_test_agent(tools=[tool_a_wrapped, tool_b_wrapped])

    # All tools (exactly what was provided)
    assert len(agent.all_tools) == 2

    # Filter to specific tools
    filtered = agent._filter_tools_by_name(["tool_a"])
    assert len(filtered) == 1
    assert filtered[0].name == "tool_a"

    # Filter to multiple tools
    filtered = agent._filter_tools_by_name(["tool_a", "tool_b"])
    assert len(filtered) == 2
    tool_names = [t.name for t in filtered]
    assert "tool_a" in tool_names
    assert "tool_b" in tool_names


def test_get_tools_for_turn_default():
    """Test that get_tools_for_turn returns None for default behavior."""
    test_tool = Tool(lambda x: x, name="test_tool")
    agent = create_test_agent(tools=[test_tool])

    # No opts - should return None (use default)
    result = agent._get_tools_for_turn(None)
    assert result is None

    # Empty opts - should return None (use default)
    result = agent._get_tools_for_turn({})
    assert result is None

    # Opts with other keys - should return None (use default)
    result = agent._get_tools_for_turn({"temperature": 0.5})
    assert result is None


def test_get_tools_for_turn_with_override():
    """Test that get_tools_for_turn respects tool overrides."""

    def tool_a(x: int) -> int:
        """Tool A."""
        return x * 2

    def tool_b(x: int) -> int:
        """Tool B."""
        return x * 3

    tool_a_wrapped = Tool(tool_a, name="tool_a")
    tool_b_wrapped = Tool(tool_b, name="tool_b")

    agent = create_test_agent(tools=[tool_a_wrapped, tool_b_wrapped])

    # Override with specific tools
    result = agent._get_tools_for_turn({"tools": ["tool_a"]})
    assert len(result) == 1
    assert result[0].name == "tool_a"

    # Override with empty list (no tools)
    result = agent._get_tools_for_turn({"tools": []})
    assert len(result) == 0

    # Override with None (use default)
    result = agent._get_tools_for_turn({"tools": None})
    assert result is None


def test_agent_repr():
    """Test agent string representation."""
    test_tool = Tool(lambda x: x, name="test_tool")
    agent = create_test_agent(tools=[test_tool])

    repr_str = repr(agent)
    assert "test_agent" in repr_str
    # Repr shows message count, not tool count
    assert "messages" in repr_str


def test_filter_nonexistent_tools():
    """Test filtering for tools that don't exist returns empty list."""

    def my_tool(x: int) -> int:
        """My tool."""
        return x

    my_tool_wrapped = Tool(my_tool, name="my_tool")
    agent = create_test_agent(tools=[my_tool_wrapped])

    # Filter for nonexistent tool
    filtered = agent._filter_tools_by_name(["nonexistent"])
    assert len(filtered) == 0


def test_filter_partial_match():
    """Test filtering with mix of existing and nonexistent tools."""

    def tool_a(x: int) -> int:
        """Tool A."""
        return x * 2

    def tool_b(x: int) -> int:
        """Tool B."""
        return x * 3

    tool_a_wrapped = Tool(tool_a, name="tool_a")
    tool_b_wrapped = Tool(tool_b, name="tool_b")

    agent = create_test_agent(tools=[tool_a_wrapped, tool_b_wrapped])

    # Filter with mix of existing and nonexistent
    filtered = agent._filter_tools_by_name(["tool_a", "nonexistent", "also_nonexistent"])
    assert len(filtered) == 1
    assert filtered[0].name == "tool_a"


def test_agent_with_state_primitive():
    """Test that agent can be initialized with state primitive."""
    state = StatePrimitive()
    state.set("key", "value")

    agent = create_test_agent(state_primitive=state)

    # Agent should have state primitive
    assert agent.deps.state_primitive is state
    assert agent.deps.state_primitive.get("key") == "value"


def test_agent_with_context():
    """Test that agent can be initialized with context."""
    context = {"custom_key": "custom_value"}

    agent = create_test_agent(context=context)

    # Agent should have context
    assert agent.deps.context == context


def test_agent_tools_with_complex_signatures():
    """Test that agent handles tools with complex parameter signatures."""

    def complex_tool(
        required: str,
        optional: int = 10,
        keyword_only: bool = False,
    ) -> dict:
        """Tool with complex signature."""
        return {
            "required": required,
            "optional": optional,
            "keyword_only": keyword_only,
        }

    complex_tool_wrapped = Tool(complex_tool, name="complex_tool")
    agent = create_test_agent(tools=[complex_tool_wrapped])

    # Should successfully create agent with exactly the tools provided
    assert len(agent.all_tools) == 1
    tool = next(t for t in agent.all_tools if t.name == "complex_tool")
    assert tool.description == "Tool with complex signature."


def test_multiple_agents_independent_tools():
    """Test that multiple agents can have independent tool sets."""

    def tool_a(x: int) -> int:
        """Tool A."""
        return x * 2

    def tool_b(x: int) -> int:
        """Tool B."""
        return x * 3

    tool_a_wrapped = Tool(tool_a, name="tool_a")
    tool_b_wrapped = Tool(tool_b, name="tool_b")

    agent1 = create_test_agent(name="agent1", tools=[tool_a_wrapped])
    agent2 = create_test_agent(name="agent2", tools=[tool_b_wrapped])

    # Agents should have independent tool sets (exactly what was provided)
    agent1_tools = [t.name for t in agent1.all_tools]
    agent2_tools = [t.name for t in agent2.all_tools]

    assert "tool_a" in agent1_tools
    assert "tool_a" not in agent2_tools
    assert "tool_b" not in agent1_tools
    assert "tool_b" in agent2_tools

    # Each agent has exactly one tool
    assert len(agent1_tools) == 1
    assert len(agent2_tools) == 1
