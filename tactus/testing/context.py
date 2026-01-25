"""
Test context for Tactus BDD testing.

Provides the context object passed to step definitions,
with helper methods to access procedure execution results.
"""

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class TactusTestContext:
    """
    Context object passed to step definitions.

    Provides access to procedure execution results and state
    for making assertions in step functions.
    """

    def __init__(
        self,
        procedure_file: Path,
        params: Optional[Dict] = None,
        mock_tools: Optional[Dict] = None,
        mcp_servers: Optional[Dict] = None,
        tool_paths: Optional[List[str]] = None,
        mocked: bool = False,
    ):
        self.procedure_file = procedure_file
        self.params = params or {}
        self.mock_tools = mock_tools  # tool_name -> mock_response
        self.mcp_servers = mcp_servers or {}
        self.tool_paths = tool_paths or []
        self.mocked = mocked  # Whether to use mocked dependencies
        self.mock_registry = None  # Unified mock registry for dependencies + HITL
        self.runtime = None
        self.execution_result: Optional[Dict] = None
        self._primitives: Dict[str, Any] = {}  # Captured primitives
        self._procedure_executed = False
        self.total_cost: float = 0.0  # Track total cost
        self.total_tokens: int = 0  # Track total tokens
        self.cost_breakdown: List[Any] = []  # Track per-call costs
        self._agent_mock_turns: Dict[str, List[Dict[str, Any]]] = {}
        self._scenario_message: str | None = None

    def set_scenario_message(self, message: str) -> None:
        """Set the scenario's primary injected message (for in-spec mocking coordination)."""
        self._scenario_message = message

    def get_scenario_message(self) -> str | None:
        """Get the scenario's primary injected message, if set."""
        return self._scenario_message

    def mock_agent_response(
        self, agent: str, message: str, when_message: str | None = None
    ) -> None:
        """Add a mocked agent response for this scenario (temporal; 1 per agent turn).

        If `when_message` is provided, the mock is selected when the agent is called
        with that exact injected message.
        """
        turn: Dict[str, Any] = {"message": message}
        effective_when = when_message if when_message is not None else self._scenario_message
        if effective_when is not None:
            turn["when_message"] = effective_when
        self._agent_mock_turns.setdefault(agent, []).append(turn)

        # Ensure runtime exists and sees the same dict reference for this scenario.
        if self.runtime is None:
            self.setup_runtime()
        if self.runtime is not None:
            self.runtime.external_agent_mocks = self._agent_mock_turns

    def mock_agent_tool_call(
        self,
        agent: str,
        tool: str,
        args: Dict[str, Any] | None = None,
        when_message: str | None = None,
    ) -> None:
        """Add a mocked tool call to an agent's next mocked turn for this scenario."""
        args = args or {}

        effective_when = when_message if when_message is not None else self._scenario_message
        if (
            agent in self._agent_mock_turns
            and self._agent_mock_turns[agent]
            and (
                effective_when is None
                or self._agent_mock_turns[agent][-1].get("when_message") == effective_when
            )
        ):
            turn = self._agent_mock_turns[agent][-1]
        else:
            turn = {}
            if effective_when is not None:
                turn["when_message"] = effective_when
            self._agent_mock_turns.setdefault(agent, []).append(turn)

        tool_calls = turn.get("tool_calls")
        if not isinstance(tool_calls, list):
            tool_calls = []
            turn["tool_calls"] = tool_calls

        tool_calls.append({"tool": tool, "args": args})

        if self.runtime is None:
            self.setup_runtime()
        if self.runtime is not None:
            self.runtime.external_agent_mocks = self._agent_mock_turns

    def mock_agent_data(
        self, agent: str, data: Dict[str, Any], when_message: str | None = None
    ) -> None:
        """Set structured output mock data for an agent's next mocked turn.

        This is only used when an agent has an output schema; the DSPy agent mock
        logic will apply `data` as the structured `result.output`.
        """
        if not isinstance(data, dict):
            raise TypeError("mock_agent_data expects a dict")

        effective_when = when_message if when_message is not None else self._scenario_message
        if (
            agent in self._agent_mock_turns
            and self._agent_mock_turns[agent]
            and (
                effective_when is None
                or self._agent_mock_turns[agent][-1].get("when_message") == effective_when
            )
        ):
            turn = self._agent_mock_turns[agent][-1]
        else:
            turn = {}
            if effective_when is not None:
                turn["when_message"] = effective_when
            self._agent_mock_turns.setdefault(agent, []).append(turn)

        turn["data"] = data

        if self.runtime is None:
            self.setup_runtime()
        if self.runtime is not None:
            self.runtime.external_agent_mocks = self._agent_mock_turns

    def mock_tool_returns(self, tool: str, output: Any) -> None:
        """Configure a runtime tool mock (Mocks { tool = { returns = ... } } equivalent)."""
        if self.runtime is None:
            self.setup_runtime()
        if self.runtime is None:
            raise AssertionError("Runtime not initialized")

        if self.runtime.mock_manager is None:
            from tactus.core.mocking import MockManager

            self.runtime.mock_manager = MockManager()

        self.runtime.mock_manager.register_mock(tool, {"output": output})
        self.runtime.mock_manager.enable_mock(tool)

    def setup_runtime(self) -> None:
        """Initialize TactusRuntime with storage and handlers."""
        import os
        from tactus.core.runtime import TactusRuntime
        from tactus.adapters.memory import MemoryStorage
        from tactus.testing.mock_hitl import MockHITLHandler
        from tactus.testing.mock_registry import UnifiedMockRegistry
        from tactus.adapters.cli_log import CLILogHandler

        storage = MemoryStorage()

        # Setup mock registry if in mocked mode
        if self.mocked:
            from tactus.testing.mock_hitl import MockHITLHandler

            self.mock_registry = UnifiedMockRegistry(hitl_handler=MockHITLHandler())
            hitl = self.mock_registry.get_hitl_handler()
            logger.info("Mock mode enabled - using UnifiedMockRegistry")
        else:
            hitl = MockHITLHandler()  # Auto-approve for tests

        log_handler = CLILogHandler()  # Capture cost events

        # Setup mocked tool primitive if mocks configured
        tool_primitive = None
        if self.mock_tools:
            self._setup_mock_tools()
            tool_primitive = self._mocked_tool_primitive
            logger.info("Mock mode enabled - using MockedToolPrimitive")

        self.runtime = TactusRuntime(
            procedure_id=f"test_{self.procedure_file.stem}",
            storage_backend=storage,
            hitl_handler=hitl,
            tool_primitive=tool_primitive,  # Inject mocked tool if configured
            openai_api_key=os.environ.get("OPENAI_API_KEY"),  # Pass API key for real LLM calls
            log_handler=log_handler,  # Enable cost tracking
            source_file_path=str(self.procedure_file.resolve()),  # For require() path resolution
            mcp_servers=self.mcp_servers,
            tool_paths=self.tool_paths,
        )

        # Create MockManager for handling Mocks {} blocks when in mocked mode
        if self.mocked or self.mock_tools:
            from tactus.core.mocking import MockManager

            self.runtime.mock_manager = MockManager()
            logger.info("Created MockManager for Mocks {} block support")
            # Mocked-mode tests should never call real LLMs by default.
            self.runtime.mock_all_agents = True

        logger.debug(f"Setup runtime for test: {self.procedure_file.stem}")

    async def run_procedure_async(self) -> None:
        """Execute procedure asynchronously and capture results."""
        if self._procedure_executed:
            logger.debug("Procedure already executed, skipping")
            return

        if not self.runtime:
            self.setup_runtime()

        # Read procedure source
        source = self.procedure_file.read_text()

        # Setup mock tools if provided
        if self.mock_tools:
            self._setup_mock_tools()

        # Inject mocked dependencies if in mocked mode
        if self.mocked and self.mock_registry:
            await self._inject_mocked_dependencies()

        # Execute procedure
        logger.info(f"Executing procedure: {self.procedure_file}")
        self.execution_result = await self.runtime.execute(
            source=source, context=self.params, format="lua"
        )

        # Capture metrics from execution result
        if self.execution_result:
            self.total_cost = self.execution_result.get("total_cost", 0.0)
            self.total_tokens = self.execution_result.get("total_tokens", 0)
            self.cost_breakdown = self.execution_result.get("cost_breakdown", [])
            self.iterations = self.execution_result.get("iterations", 0)
            self.tools_used = self.execution_result.get("tools_used", [])

        # Capture primitives for assertions
        self._capture_primitives()

        self._procedure_executed = True
        logger.info(f"Procedure execution complete: success={self.execution_result.get('success')}")

    def run_procedure(self) -> None:
        """Execute procedure synchronously (wrapper for async)."""
        asyncio.run(self.run_procedure_async())

    def _setup_mock_tools(self) -> None:
        """Setup mock tool responses by creating MockedToolPrimitive."""
        from tactus.testing.mock_tools import MockToolRegistry, MockedToolPrimitive

        # Create mock registry
        mock_registry = MockToolRegistry()
        for tool_name, response in self.mock_tools.items():
            mock_registry.register(tool_name, response)

        # Create mocked tool primitive
        self._mocked_tool_primitive = MockedToolPrimitive(mock_registry)

        logger.info(f"Mock tools configured: {list(self.mock_tools.keys())}")

    async def _inject_mocked_dependencies(self) -> None:
        """Inject mocked dependencies into runtime."""
        if not self.runtime or not self.runtime.registry:
            logger.warning("Cannot inject mocked dependencies - runtime or registry not available")
            return

        # Get dependencies from registry
        dependencies_config = {}
        for dep_name, dep_decl in self.runtime.registry.dependencies.items():
            dependencies_config[dep_name] = dep_decl.config

        if not dependencies_config:
            logger.debug("No dependencies declared in procedure")
            return

        # Create mock dependencies
        mock_dependencies = await self.mock_registry.create_mock_dependencies(dependencies_config)

        # Inject into runtime
        self.runtime.user_dependencies = mock_dependencies

        logger.info(f"Mocked dependencies injected: {list(mock_dependencies.keys())}")

    def _capture_primitives(self) -> None:
        """Capture primitive states after execution."""
        if not self.runtime or not self.runtime.lua_sandbox:
            logger.warning("Cannot capture primitives - runtime or sandbox not available")
            return

        # Capture Tool primitive
        try:
            self._primitives["tool"] = self.runtime.tool_primitive
        except Exception as e:
            logger.debug(f"Could not capture Tool primitive: {e}")

        # Capture State primitive
        try:
            self._primitives["state"] = self.runtime.state_primitive
        except Exception as e:
            logger.debug(f"Could not capture State primitive: {e}")

        # Capture Iterations primitive
        try:
            self._primitives["iterations"] = self.runtime.iterations_primitive
        except Exception as e:
            logger.debug(f"Could not capture Iterations primitive: {e}")

        # Capture Stop primitive
        try:
            self._primitives["stop"] = self.runtime.stop_primitive
        except Exception as e:
            logger.debug(f"Could not capture Stop primitive: {e}")

        logger.debug(f"Captured {len(self._primitives)} primitives")

    def is_running(self) -> bool:
        """Check if procedure has been executed."""
        return self._procedure_executed

    # Tool-related methods

    def tool_called(self, tool_name: str) -> bool:
        """Check if a tool was called."""
        tool_prim = self._primitives.get("tool")
        if tool_prim:
            return tool_prim.called(tool_name)
        # Fallback to execution result
        tools_used = self.execution_result.get("tools_used", []) if self.execution_result else []
        return tool_name in tools_used

    def tool_call_count(self, tool_name: str) -> int:
        """Get number of times a tool was called."""
        tool_prim = self._primitives.get("tool")
        if tool_prim and hasattr(tool_prim, "_tool_calls"):
            return sum(1 for call in tool_prim._tool_calls if call.name == tool_name)
        return 0

    def tool_calls(self, tool_name: str) -> List[Dict]:
        """Get all calls to a specific tool."""
        tool_prim = self._primitives.get("tool")
        if tool_prim and hasattr(tool_prim, "_tool_calls"):
            return [
                {"tool": call.name, "args": call.args, "result": call.result}
                for call in tool_prim._tool_calls
                if call.name == tool_name
            ]
        return []

    # State-related methods

    def state_get(self, key: str) -> Any:
        """Get state value."""
        state_prim = self._primitives.get("state")
        if state_prim:
            return state_prim.get(key)
        return None

    def state_exists(self, key: str) -> bool:
        """Check if state key exists."""
        state_prim = self._primitives.get("state")
        if state_prim and hasattr(state_prim, "_state"):
            return key in state_prim._state
        return False

    # Output-related methods

    def output_get(self, key: str) -> Any:
        """Get output value from procedure execution result."""
        if self.execution_result:
            # Check if outputs are in a dedicated field
            if "output" in self.execution_result:
                output = self.execution_result["output"]
                if isinstance(output, dict):
                    return output.get(key)
                return None
            # Otherwise check in the result dict (procedure return value)
            if "result" in self.execution_result:
                result = self.execution_result["result"]
                if isinstance(result, dict):
                    return result.get(key)

        return None

    def output_exists(self, key: str) -> bool:
        """Check if output key exists in procedure execution result."""
        if self.execution_result:
            # Check if outputs are in a dedicated field
            if "output" in self.execution_result:
                output = self.execution_result["output"]
                return isinstance(output, dict) and key in output
            # Otherwise check in the result dict (procedure return value)
            if "result" in self.execution_result:
                result = self.execution_result["result"]
                if isinstance(result, dict):
                    return key in result
        return False

    def output_value(self) -> Any:
        """Get the full (possibly scalar) output value for the procedure."""
        if not self.execution_result:
            return None
        if "output" in self.execution_result:
            return self.execution_result["output"]
        result = self.execution_result.get("result")
        try:
            from tactus.protocols.result import TactusResult

            if isinstance(result, TactusResult):
                return result.output
        except Exception:
            pass
        return result

    # Completion methods

    def stop_success(self) -> bool:
        """Check if procedure completed successfully."""
        if self.execution_result:
            return self.execution_result.get("success", False)
        return False

    def stop_reason(self) -> str:
        """Get stop reason."""
        stop_prim = self._primitives.get("stop")
        if stop_prim and hasattr(stop_prim, "_reason"):
            return stop_prim._reason or ""
        if self.execution_result:
            return self.execution_result.get("stop_reason", "")
        return ""

    # Iteration methods

    def iterations(self) -> int:
        """Get total iterations."""
        iterations_prim = self._primitives.get("iterations")
        if iterations_prim and hasattr(iterations_prim, "_count"):
            return iterations_prim._count
        if self.execution_result:
            return self.execution_result.get("iterations", 0)
        return 0

    def agent_turns(self) -> int:
        """Get number of agent turns."""
        # Count from execution result
        if self.execution_result:
            return self.execution_result.get("agent_turns", 0)
        return 0

    # Parameter/context methods

    def get_params(self) -> Dict:
        """Get procedure parameters."""
        return self.params

    def set_input(self, key: str, value: Any) -> None:
        """Set an input parameter for the procedure.

        Args:
            key: Parameter name
            value: Parameter value (will be parsed from string if needed)
        """
        self.params[key] = value
        logger.debug(f"Set input parameter: {key}={value}")

    def agent_context(self) -> str:
        """Get agent context as string."""
        # This would need to be populated by the runtime
        if self.execution_result:
            return self.execution_result.get("agent_context", "")
        return ""
