"""
Mock agent primitive for BDD testing.

Provides mock agent that simulates turns without LLM calls.
Uses agent mock configurations from Mocks {} in .tac files.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MockUsageStats:
    """Mock usage stats for compatibility with TactusResult.usage."""

    def __init__(self):
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0


class MockAgentResult:
    """Result from a mock agent turn - matches TactusResult interface."""

    def __init__(
        self, message: str = "", tool_calls: Optional[List[Dict]] = None, data: Any = None
    ):
        self.message = message
        self.tool_calls = tool_calls or []
        self.cost = 0.0
        self.tokens = 0
        # value matches TactusResult.value - use structured data if provided, else message
        self.value = data if data is not None else message
        # usage matches TactusResult.usage
        self.usage = MockUsageStats()

    def __repr__(self) -> str:
        return f"MockAgentResult(message={self.message!r}, tool_calls={len(self.tool_calls)})"


class MockAgentPrimitive:
    """
    Mock agent that simulates turns without making LLM calls.

    Uses agent mock configurations from Mocks {} in .tac files.
    The mock config specifies exactly which tool calls to simulate,
    allowing tests to pass in CI without real LLM calls.

    Example Mocks {} configuration:
        Mocks {
            my_agent = {
                tool_calls = {
                    {tool = "search", args = {query = "test"}},
                    {tool = "done", args = {reason = "completed"}}
                },
                message = "I found the results."
            }
        }
    """

    def __init__(
        self,
        name: str,
        tool_primitive: Any,
        registry: Any = None,
        mock_manager: Any = None,
    ):
        """
        Initialize mock agent.

        Args:
            name: Agent name
            tool_primitive: ToolPrimitive for recording tool calls
            registry: Registry containing agent_mocks configuration
            mock_manager: Optional MockManager (for tool response mocking)
        """
        self.name = name
        self.tool_primitive = tool_primitive
        self.registry = registry
        self.mock_manager = mock_manager
        self.turn_count = 0

    def turn(self, opts: Optional[Dict[str, Any]] = None) -> MockAgentResult:
        """
        Simulate an agent turn by executing configured tool calls.

        Looks up agent mock config in registry.agent_mocks and executes
        the specified tool calls, then returns the configured message.

        Args:
            opts: Optional turn options (for compatibility)

        Returns:
            MockAgentResult with message and tool call info

        Raises:
            ValueError: If no mock config is found for this agent
        """
        opts = opts or {}
        self.turn_count += 1
        logger.info(f"Mock agent turn: {self.name} (turn {self.turn_count})")

        # Get agent mock config
        mock_config = self._get_agent_mock_config()

        if mock_config is None:
            raise ValueError(
                f"Agent '{self.name}' requires mock config in Mocks {{}}. "
                f"Add a mock configuration like:\n"
                f"Mocks {{\n"
                f"    {self.name} = {{\n"
                f"        tool_calls = {{\n"
                f'            {{tool = "done", args = {{reason = "completed"}}}}\n'
                f"        }},\n"
                f'        message = "Task completed."\n'
                f"    }}\n"
                f"}}"
            )

        # Execute the configured tool calls
        tool_calls_executed = self._execute_tool_calls(mock_config.tool_calls)

        # Return the configured message and data
        return MockAgentResult(
            message=mock_config.message,
            tool_calls=tool_calls_executed,
            data=mock_config.data,
        )

    def _get_agent_mock_config(self) -> Optional[Any]:
        """
        Get agent mock config from registry.agent_mocks.

        Returns:
            AgentMockConfig if found, None otherwise
        """
        if not self.registry:
            return None

        # Check for agent mock in registry.agent_mocks
        if hasattr(self.registry, "agent_mocks"):
            return self.registry.agent_mocks.get(self.name)

        return None

    def _execute_tool_calls(self, tool_calls: List[Dict[str, Any]]) -> List[Dict]:
        """
        Execute the configured tool calls.

        Records each tool call via the tool_primitive, which will
        use mock responses from the MockManager if configured.

        Args:
            tool_calls: List of tool call configs [{tool: "name", args: {...}}, ...]

        Returns:
            List of executed tool calls with results
        """
        executed = []

        for tool_call in tool_calls:
            tool_name = tool_call.get("tool")
            args = tool_call.get("args", {})

            if not tool_name:
                logger.warning(f"Skipping invalid tool call config: {tool_call}")
                continue

            logger.debug(f"Mock agent {self.name} executing tool call: {tool_name}({args})")

            # Record the tool call via tool primitive
            # Default result for mock tool calls
            result = {"status": "ok", "tool": tool_name, "args": args}
            if self.tool_primitive:
                try:
                    # record_call records the tool call for assertions
                    self.tool_primitive.record_call(tool_name, args, result)
                except Exception as e:
                    logger.warning(f"Error recording tool call {tool_name}: {e}")

            executed.append(
                {
                    "tool": tool_name,
                    "args": args,
                    "result": result,
                }
            )

        return executed

    def __call__(self, inputs: Optional[Dict[str, Any]] = None) -> MockAgentResult:
        """
        Execute an agent turn using the callable interface.

        This makes the mock agent callable like real agents:
            result = worker({message = "Hello"})

        Args:
            inputs: Input dict (ignored in mock mode, tool calls are from config)

        Returns:
            MockAgentResult with response and tool call info
        """
        inputs = inputs or {}

        # Convert Lua table to dict if needed
        if hasattr(inputs, "items"):
            try:
                inputs = dict(inputs.items())
            except (AttributeError, TypeError):
                pass

        # Extract message field for logging
        message = inputs.get("message", "")
        if message:
            logger.debug(f"Mock agent {self.name} received message: {message}")

        # Execute the turn (tool calls come from config, not inputs)
        return self.turn(inputs)

    def __repr__(self) -> str:
        return f"MockAgentPrimitive({self.name}, turns={self.turn_count})"
