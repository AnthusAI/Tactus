"""
Mock agent primitive for BDD testing.

Provides mock agent that simulates turns without LLM calls.
Uses agent mock configurations from Mocks {} in .tac files.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MockAgentResult:
    """Result from a mock agent turn."""

    def __init__(
        self,
        message: str = "",
        tool_calls: Optional[List[Dict]] = None,
        data: Optional[Dict[str, Any]] = None,
        usage: Optional[Dict[str, Any]] = None,
        new_messages: Optional[List[Dict[str, Any]]] = None,
        lua_table_from: Optional[Any] = None,
    ):
        self.message = message
        self.response = message
        self.tool_calls = tool_calls or []
        self.data = data or {}
        self.usage = usage or {}
        self.cost = 0.0
        try:
            self.tokens = int(self.usage.get("total_tokens", 0) or 0)
        except Exception:
            self.tokens = 0

        self._new_messages = new_messages or []
        self._lua_table_from = lua_table_from

    def __repr__(self) -> str:
        return (
            f"MockAgentResult(message={self.message!r}, tool_calls={len(self.tool_calls)}, "
            f"data_keys={len(self.data) if hasattr(self.data, '__len__') else 'n/a'})"
        )

    def new_messages(self):
        """
        Return messages generated in this turn.

        In Lua, callers expect a table (for `#msgs` and 1-based indexing).
        """
        if self._lua_table_from is not None:
            try:
                return self._lua_table_from(self._new_messages)
            except Exception:
                # Fall back to raw Python list if conversion fails.
                pass
        return self._new_messages


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
        lua_runtime: Any = None,
        lua_table_from: Any = None,
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
        if lua_table_from is not None:
            self._lua_table_from = lua_table_from
        elif lua_runtime is not None and hasattr(lua_runtime, "table_from"):
            self._lua_table_from = lua_runtime.table_from
        else:
            self._lua_table_from = None

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

        temporal_turns = getattr(mock_config, "temporal", None) or []
        if temporal_turns:
            injected = opts.get("message")

            selected_turn = None
            if injected is not None:
                for turn in temporal_turns:
                    if isinstance(turn, dict) and turn.get("when_message") == injected:
                        selected_turn = turn
                        break

            if selected_turn is None:
                idx = self.turn_count - 1  # 1-indexed turns
                if idx < 0:
                    idx = 0
                if idx >= len(temporal_turns):
                    idx = len(temporal_turns) - 1
                selected_turn = temporal_turns[idx]

            turn = selected_turn
            if isinstance(turn, dict):
                message = turn.get("message", mock_config.message)
                tool_calls = turn.get("tool_calls", mock_config.tool_calls)
                data = turn.get("data", mock_config.data)
                raw_usage = turn.get("usage", mock_config.usage)
            else:
                message = mock_config.message
                tool_calls = mock_config.tool_calls
                data = mock_config.data
                raw_usage = mock_config.usage
        else:
            message = mock_config.message
            tool_calls = mock_config.tool_calls
            data = mock_config.data
            raw_usage = mock_config.usage

        # Execute the configured tool calls
        tool_calls_executed = self._execute_tool_calls(tool_calls)

        # Structured payload (optional) for result.data
        data = data or {}
        if not data:
            data = {"response": message}

        # Token usage payload (optional) for result.usage
        usage = dict(raw_usage) if isinstance(raw_usage, dict) else {}
        prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
        completion_tokens = int(usage.get("completion_tokens", 0) or 0)
        total_tokens = usage.get("total_tokens")
        if total_tokens is None:
            total_tokens = prompt_tokens + completion_tokens
        total_tokens = int(total_tokens or 0)
        usage.setdefault("prompt_tokens", prompt_tokens)
        usage.setdefault("completion_tokens", completion_tokens)
        usage.setdefault("total_tokens", total_tokens)

        # Messages generated in this turn
        user_message = opts.get("message")
        new_messages = []
        if user_message:
            new_messages.append({"role": "user", "content": user_message})
        if message:
            new_messages.append({"role": "assistant", "content": message})

        # Return the configured message
        return MockAgentResult(
            message=message,
            tool_calls=tool_calls_executed,
            data=data,
            usage=usage,
            new_messages=new_messages,
            lua_table_from=self._lua_table_from,
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
            # MockedToolPrimitive.record_call(tool_name, args) returns the mock response
            result = None
            if self.tool_primitive:
                try:
                    # record_call returns the mock response and records the call
                    result = self.tool_primitive.record_call(tool_name, args)
                except Exception as e:
                    logger.warning(f"Error recording tool call {tool_name}: {e}")
                    result = {"status": "ok", "tool": tool_name}

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
