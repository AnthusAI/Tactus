"""
Mock agent primitive for BDD testing.

Provides mock agent that simulates turns without LLM calls.
"""

import logging
from typing import Any, Optional


logger = logging.getLogger(__name__)


class MockAgentPrimitive:
    """
    Mock agent that simulates turns without making LLM calls.

    Useful for:
    - Fast, deterministic tests
    - Testing without API keys
    - Workflow logic validation
    """

    def __init__(self, name: str, tool_primitive: Any):
        """
        Initialize mock agent.

        Args:
            name: Agent name
            tool_primitive: ToolPrimitive for recording tool calls
        """
        self.name = name
        self.tool_primitive = tool_primitive
        self.turn_count = 0

    def turn(self, message: Optional[str] = None) -> Any:
        """
        Simulate an agent turn without LLM calls.

        Args:
            message: Optional message to agent (ignored in mock)

        Returns:
            None (mocked agents don't return values)
        """
        self.turn_count += 1
        logger.info(f"Mock agent turn: {self.name} (turn {self.turn_count})")

        # Simulate calling done tool after first turn
        # This allows procedures with "until Tool.called('done')" to complete
        if self.turn_count == 1 and self.tool_primitive:
            logger.debug(f"Mock agent {self.name} calling 'done' tool")
            # Check if it's a MockedToolPrimitive (takes 2 args) or regular (takes 3 args)
            from tactus.testing.mock_tools import MockedToolPrimitive

            # Provide a mock greeting message that procedures might expect
            mock_args = {"reason": f"Mock greeting from {self.name}"}

            if isinstance(self.tool_primitive, MockedToolPrimitive):
                # MockedToolPrimitive.record_call(tool_name, args) -> returns result
                self.tool_primitive.record_call("done", mock_args)
            else:
                # Regular ToolPrimitive.record_call(tool_name, args, result)
                self.tool_primitive.record_call("done", mock_args, {"status": "mocked"})

        return None

    def __repr__(self) -> str:
        return f"MockAgentPrimitive({self.name}, turns={self.turn_count})"
