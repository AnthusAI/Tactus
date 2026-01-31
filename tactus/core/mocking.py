"""
Mocking infrastructure for Tactus.

Provides comprehensive mocking capabilities including:
- Static mocks (always return same value)
- Temporal mocks (different returns per call)
- Conditional mocks (based on input parameters)
- Mock state tracking and assertions
"""

from dataclasses import dataclass, field
import logging
from typing import Any, Optional, Union

logger = logging.getLogger(__name__)


@dataclass
class MockCall:
    """Record of a mock tool call."""

    tool_name: str
    args: dict[str, Any]
    result: Any
    call_number: int
    timestamp: float


@dataclass
class MockConfig:
    """Configuration for a mocked tool."""

    tool_name: str

    # Static mock - always returns this
    static_result: Optional[Any] = None

    # Temporal mocks - return different values per call
    temporal_results: list[Any] = field(default_factory=list)

    # Conditional mocks - return based on args
    conditional_mocks: list[dict[str, Any]] = field(default_factory=list)

    # Error simulation
    error: Optional[str] = None

    # Whether this mock is enabled
    enabled: bool = True


class MockManager:
    """
    Manages mock state and temporal mocking for testing.

    This is injected into the runtime to intercept tool calls
    and return mock responses when configured.
    """

    def __init__(self):
        """Initialize mock manager."""
        self.mocks: dict[str, MockConfig] = {}
        self.call_history: dict[str, list[MockCall]] = {}
        self.call_counts: dict[str, int] = {}
        self.enabled = True  # Global mock enable/disable

    def register_mock(self, tool_name: str, config: Union[MockConfig, dict[str, Any]]) -> None:
        """
        Register a mock configuration for a tool.

        Args:
            tool_name: Name of the tool to mock
            config: MockConfig or dict with mock settings
        """
        if isinstance(config, dict):
            # Convert dict to MockConfig
            if "output" in config:
                # Simple static mock
                mock_config = MockConfig(tool_name=tool_name, static_result=config["output"])
            elif "error" in config:
                # Error simulation
                mock_config = MockConfig(tool_name=tool_name, error=config["error"])
            elif "temporal" in config:
                # Temporal mocking
                mock_config = MockConfig(tool_name=tool_name, temporal_results=config["temporal"])
            else:
                # Full config
                mock_config = MockConfig(tool_name=tool_name, **config)
        else:
            mock_config = config

        self.mocks[tool_name] = mock_config
        logger.info("Registered mock for tool '%s'", tool_name)

    def get_mock_response(self, tool_name: str, args: dict[str, Any]) -> Optional[Any]:
        """
        Get mock response for a tool call.

        Args:
            tool_name: Name of the tool being called
            args: Arguments passed to the tool

        Returns:
            Mock response if configured, None if tool should run normally
        """
        if not self.enabled:
            return None

        if tool_name not in self.mocks:
            return None

        mock_config = self.mocks[tool_name]
        if not mock_config.enabled:
            return None

        # Get call number for this tool
        call_number = self.call_counts.get(tool_name, 0) + 1

        # Check for error simulation
        if mock_config.error:
            raise RuntimeError(mock_config.error)

        # Check temporal mocks first
        if mock_config.temporal_results:
            # Return based on call number (1-indexed)
            if call_number <= len(mock_config.temporal_results):
                result = mock_config.temporal_results[call_number - 1]
                logger.debug(
                    "Mock '%s' returning temporal result for call %s: %s",
                    tool_name,
                    call_number,
                    result,
                )
                return result
            else:
                # Fallback to last result if we've exceeded temporal results
                result = mock_config.temporal_results[-1]
                logger.debug(
                    "Mock '%s' returning last temporal result (call %s): %s",
                    tool_name,
                    call_number,
                    result,
                )
                return result

        # Check conditional mocks
        for conditional in mock_config.conditional_mocks:
            condition = conditional.get("when", {})
            if self._matches_condition(args, condition):
                result = conditional.get("return")
                logger.debug(
                    "Mock '%s' matched condition, returning: %s",
                    tool_name,
                    result,
                )
                return result

        # Return static result if configured
        if mock_config.static_result is not None:
            logger.debug(
                "Mock '%s' returning static result: %s",
                tool_name,
                mock_config.static_result,
            )
            return mock_config.static_result

        # No mock response configured
        return None

    def record_call(self, tool_name: str, args: dict[str, Any], result: Any) -> None:
        """
        Record a tool call for assertions.

        Args:
            tool_name: Name of the tool that was called
            args: Arguments passed to the tool
            result: Result returned by the tool (or mock)
        """
        import time

        # Update call count
        self.call_counts[tool_name] = self.call_counts.get(tool_name, 0) + 1

        # Create call record
        call = MockCall(
            tool_name=tool_name,
            args=args,
            result=result,
            call_number=self.call_counts[tool_name],
            timestamp=time.time(),
        )

        # Add to history
        if tool_name not in self.call_history:
            self.call_history[tool_name] = []
        self.call_history[tool_name].append(call)

        logger.debug("Recorded call to '%s' (call #%s)", tool_name, call.call_number)

    def get_call_count(self, tool_name: str) -> int:
        """
        Get the number of times a tool was called.

        Args:
            tool_name: Name of the tool

        Returns:
            Number of calls to the tool
        """
        return self.call_counts.get(tool_name, 0)

    def get_call_history(self, tool_name: str) -> list[MockCall]:
        """
        Get the call history for a tool.

        Args:
            tool_name: Name of the tool

        Returns:
            List of MockCall records
        """
        return self.call_history.get(tool_name, [])

    def reset(self) -> None:
        """Reset all mock state."""
        self.call_history.clear()
        self.call_counts.clear()
        logger.debug("Mock manager state reset")

    def _matches_condition(self, args: dict[str, Any], condition: dict[str, Any]) -> bool:
        """
        Check if args match a condition.

        Args:
            args: Tool arguments to check
            condition: Condition dict with patterns to match

        Returns:
            True if condition matches
        """
        for key, pattern in condition.items():
            if key not in args:
                return False

            argument_value = args[key]

            # Handle different pattern types
            if isinstance(pattern, str):
                # Check for operators
                if pattern.startswith("contains:"):
                    substring = pattern[9:].strip()
                    if substring not in str(argument_value):
                        return False
                elif pattern.startswith("startswith:"):
                    prefix = pattern[11:].strip()
                    if not str(argument_value).startswith(prefix):
                        return False
                elif pattern.startswith("endswith:"):
                    suffix = pattern[9:].strip()
                    if not str(argument_value).endswith(suffix):
                        return False
                else:
                    # Exact match
                    if argument_value != pattern:
                        return False
            else:
                # Direct comparison
                if argument_value != pattern:
                    return False

        return True

    def enable_mock(self, tool_name: Optional[str] = None) -> None:
        """
        Enable mocking for a specific tool or all tools.

        Args:
            tool_name: Specific tool to enable, or None for all
        """
        if tool_name:
            if tool_name in self.mocks:
                self.mocks[tool_name].enabled = True
                logger.info("Enabled mock for tool '%s'", tool_name)
        else:
            self.enabled = True
            logger.info("Enabled all mocks")

    def disable_mock(self, tool_name: Optional[str] = None) -> None:
        """
        Disable mocking for a specific tool or all tools.

        Args:
            tool_name: Specific tool to disable, or None for all
        """
        if tool_name:
            if tool_name in self.mocks:
                self.mocks[tool_name].enabled = False
                logger.info("Disabled mock for tool '%s'", tool_name)
        else:
            self.enabled = False
            logger.info("Disabled all mocks")
