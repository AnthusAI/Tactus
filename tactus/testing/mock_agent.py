"""
Mock agent primitive for BDD testing.

Provides mock agent that simulates turns without LLM calls.
Supports unified Mocks {} configuration from .tac files.
"""

import logging
from typing import Any, Dict, Optional


logger = logging.getLogger(__name__)


class MockAgentPrimitive:
    """
    Mock agent that simulates turns without making LLM calls.

    Supports the unified Mocks {} configuration from .tac files.
    If a mock is configured for this agent name, uses that mock response.
    Otherwise falls back to default mock behavior.

    Useful for:
    - Fast, deterministic tests
    - Testing without API keys
    - Workflow logic validation
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
            registry: Optional Registry for accessing Mocks {} configuration
            mock_manager: Optional MockManager for getting mock responses
        """
        self.name = name
        self.tool_primitive = tool_primitive
        self.registry = registry
        self.mock_manager = mock_manager
        self.turn_count = 0
        self._call_index = 0  # For temporal mocking

    def turn(self, opts: Optional[Dict[str, Any]] = None) -> Any:
        """
        Simulate an agent turn without LLM calls.

        First checks for Mocks {} configuration from the .tac file.
        Falls back to default behavior if no mock is configured.

        Args:
            opts: Optional turn options (for compatibility with DSPyAgentHandle)

        Returns:
            Mock response dict if configured, None otherwise
        """
        opts = opts or {}
        self.turn_count += 1
        logger.info(f"Mock agent turn: {self.name} (turn {self.turn_count})")

        # Check for Mocks {} configuration
        mock_response = self._get_custom_mock_response(opts)
        if mock_response is not None:
            logger.debug(f"Mock agent {self.name} using Mocks {{}} configuration")
            self._handle_mock_response(mock_response)
            return mock_response

        # No mock configured - return None without auto-calling any tools
        logger.debug(f"Mock agent {self.name} has no Mocks {{}} configuration; returning default")

        # Default: simulate a simple response and done call so workflows can progress
        default_response = {
            "response": "Task completed (mocked)",
            "message": "Task completed (mocked)",
            "tool_calls": "done",
        }
        self._handle_mock_response(default_response)
        return default_response

    def _get_custom_mock_response(self, opts: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Check if this agent has a custom mock configured in Mocks {}.

        Args:
            opts: Turn options

        Returns:
            Mock response dict if configured, None otherwise
        """
        if not self.mock_manager:
            return None

        try:
            if hasattr(self.mock_manager, "get_agent_mock_response"):
                return self.mock_manager.get_agent_mock_response(self.name, opts)
            # Fallback to explicit mock lookup
            if (
                self.registry
                and hasattr(self.registry, "mocks")
                and self.name in self.registry.mocks
            ):
                return self.mock_manager.get_mock_response(self.name, opts)
        except Exception as e:
            logger.warning(f"Error getting mock response for agent {self.name}: {e}")
            return None

        return None

    def _handle_mock_response(self, mock_response: Dict[str, Any]) -> None:
        """
        Handle a custom mock response, including tool call simulation.

        Args:
            mock_response: The mock response dict
        """
        # Check if mock simulates a tool call (e.g., "done")
        if "tool_calls" in mock_response and self.tool_primitive:
            tool_calls = mock_response.get("tool_calls", "")
            if "done" in str(tool_calls).lower():
                reason = mock_response.get("response", "Task completed (mocked)")
                self._record_done_call(reason)
        elif self.tool_primitive:
            # Default behavior: simulate a done call to unblock workflows that expect it
            reason = mock_response.get("response", "Task completed (mocked)")
            self._record_done_call(reason)

    def _record_done_call(self, reason: str) -> None:
        """
        Record a done tool call.

        Args:
            reason: The reason/message for the done call
        """
        from tactus.testing.mock_tools import MockedToolPrimitive

        mock_args = {"reason": reason}

        if isinstance(self.tool_primitive, MockedToolPrimitive):
            self.tool_primitive.record_call("done", mock_args)
        else:
            self.tool_primitive.record_call(
                "done",
                mock_args,
                {"status": "completed", "reason": reason, "tool": "done"},
                agent_name=self.name,
            )

    def __call__(self, inputs: Optional[Dict[str, Any]] = None) -> Any:
        """
        Execute an agent turn using the callable interface.

        This makes the mock agent callable like real agents:
            result = worker({message = "Hello"})

        Args:
            inputs: Input dict with fields matching input_schema.
                   Default field 'message' is used as the user message.

        Returns:
            Result object with response and other fields
        """
        inputs = inputs or {}

        # Convert Lua table to dict if needed
        if hasattr(inputs, "items"):
            try:
                inputs = dict(inputs.items())
            except (AttributeError, TypeError):
                pass

        # Extract message field (the main input)
        message = inputs.get("message")

        # Build turn options
        opts = {}
        if message:
            opts["inject"] = message

        # Pass remaining fields as context
        context = {k: v for k, v in inputs.items() if k != "message"}
        if context:
            opts["context"] = context

        # Call turn() with the mapped options
        return self.turn(opts)

    def __repr__(self) -> str:
        return f"MockAgentPrimitive({self.name}, turns={self.turn_count})"
