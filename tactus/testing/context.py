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
        mocked: bool = False,
    ):
        self.procedure_file = procedure_file
        self.params = params or {}
        self.mock_tools = mock_tools  # tool_name -> mock_response
        self.mocked = mocked  # Whether to use mocked dependencies
        self.mock_registry = None  # Unified mock registry for dependencies + HITL
        self.runtime = None
        self.execution_result: Optional[Dict] = None
        self._primitives: Dict[str, Any] = {}  # Captured primitives
        self._procedure_executed = False
        self.total_cost: float = 0.0  # Track total cost
        self.total_tokens: int = 0  # Track total tokens
        self.cost_breakdown: List[Any] = []  # Track per-call costs

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
            skip_agents=bool(self.mock_tools),  # Skip agents in mock mode
            openai_api_key=os.environ.get("OPENAI_API_KEY"),  # Pass API key for real LLM calls
            log_handler=log_handler,  # Enable cost tracking
        )

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

        # Capture Stage primitive
        try:
            self._primitives["stage"] = self.runtime.stage_primitive
        except Exception as e:
            logger.debug(f"Could not capture Stage primitive: {e}")

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

    # Stage-related methods

    def current_stage(self) -> Optional[str]:
        """Get current stage."""
        stage_prim = self._primitives.get("stage")
        if stage_prim:
            return stage_prim.current()
        return None

    def stage_history(self) -> List[str]:
        """Get stage transition history as list of stage names."""
        stage_prim = self._primitives.get("stage")
        if stage_prim and hasattr(stage_prim, "_history"):
            # Extract just the stage names from history
            stages = []
            for transition in stage_prim._history:
                if transition.get("from_stage"):
                    stages.append(transition["from_stage"])
                if transition.get("to_stage"):
                    stages.append(transition["to_stage"])
            # Remove duplicates while preserving order
            seen = set()
            result = []
            for stage in stages:
                if stage not in seen:
                    seen.add(stage)
                    result.append(stage)
            return result
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
            if "outputs" in self.execution_result:
                return self.execution_result["outputs"].get(key)
            # Otherwise check in the result dict (procedure return value)
            if "result" in self.execution_result and isinstance(
                self.execution_result["result"], dict
            ):
                return self.execution_result["result"].get(key)
        return None

    def output_exists(self, key: str) -> bool:
        """Check if output key exists in procedure execution result."""
        if self.execution_result:
            # Check if outputs are in a dedicated field
            if "outputs" in self.execution_result:
                return key in self.execution_result["outputs"]
            # Otherwise check in the result dict (procedure return value)
            if "result" in self.execution_result and isinstance(
                self.execution_result["result"], dict
            ):
                return key in self.execution_result["result"]
        return False

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

    def agent_context(self) -> str:
        """Get agent context as string."""
        # This would need to be populated by the runtime
        if self.execution_result:
            return self.execution_result.get("agent_context", "")
        return ""
