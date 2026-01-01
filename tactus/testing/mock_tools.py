"""
Mock tool system for deterministic BDD testing.

Provides mocked tool responses for fast, repeatable tests
without requiring actual LLM calls or external services.
"""

import logging
from typing import Any, Dict

from tactus.primitives.tool import ToolPrimitive, ToolCall


logger = logging.getLogger(__name__)


class MockToolRegistry:
    """
    Registry for mock tool responses.

    Maps tool names to mock responses (static or callable).
    """

    def __init__(self):
        self.mocks: Dict[str, Any] = {}

    def register(self, tool_name: str, response: Any) -> None:
        """
        Register a mock response for a tool.

        Args:
            tool_name: Name of the tool to mock
            response: Mock response (can be static value or callable)
        """
        self.mocks[tool_name] = response
        logger.debug(f"Registered mock for tool: {tool_name}")

    def get_response(self, tool_name: str, args: Dict) -> Any:
        """
        Get mock response for tool call.

        Args:
            tool_name: Name of the tool
            args: Arguments passed to the tool

        Returns:
            Mock response

        Raises:
            ValueError: If no mock registered for tool
        """
        if tool_name not in self.mocks:
            raise ValueError(f"No mock registered for tool: {tool_name}")

        response = self.mocks[tool_name]

        # Support callable mocks for dynamic responses
        if callable(response):
            return response(args)

        return response

    def has_mock(self, tool_name: str) -> bool:
        """Check if tool has a mock registered."""
        return tool_name in self.mocks

    def clear(self) -> None:
        """Clear all registered mocks."""
        self.mocks.clear()


class MockedToolPrimitive(ToolPrimitive):
    """
    Tool primitive that uses mocked responses instead of real tool execution.

    Useful for:
    - Fast, deterministic tests
    - Testing without API keys
    - Avoiding external service calls
    """

    def __init__(self, mock_registry: MockToolRegistry):
        super().__init__()
        self.mock_registry = mock_registry

    def record_call(self, tool_name: str, args: Dict[str, Any]) -> Any:
        """
        Record tool call and return mock response.

        Args:
            tool_name: Name of the tool
            args: Tool arguments

        Returns:
            Mocked tool result
        """
        # Get mock response
        result = self.mock_registry.get_response(tool_name, args)

        # Record the call (same as real ToolPrimitive)
        call = ToolCall(tool_name, args, result)
        self._tool_calls.append(call)
        self._last_calls[tool_name] = call

        logger.info(f"Mocked tool call: {tool_name}(args={args}) -> {result}")

        return result


def create_default_mocks() -> Dict[str, Any]:
    """
    Create default mock responses for common tools.

    Returns:
        Dict of tool_name -> mock_response
    """
    return {
        "done": {"status": "complete", "message": "Task completed"},
        "search": {"results": ["result1", "result2", "result3"]},
        "write_file": {"success": True, "path": "/tmp/test.txt"},
        "read_file": {"content": "test content"},
    }
