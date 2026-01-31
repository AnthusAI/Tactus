"""
Tactus Runtime - Main execution engine for Lua-based workflows.

Orchestrates:
1. Lua DSL parsing and validation (via registry)
2. Lua sandbox setup
3. Primitive injection
4. Agent configuration with LLMs and tools (optional)
5. Workflow execution
"""

import io
import logging
import time
import uuid
from typing import Any

from tactus.core.registry import ProcedureRegistry, RegistryBuilder
from tactus.core.dsl_stubs import create_dsl_stubs, lua_table_to_dict
from tactus.core.template_resolver import TemplateResolver
from tactus.core.message_history_manager import MessageHistoryManager
from tactus.core.lua_sandbox import LuaSandbox, LuaSandboxError
from tactus.core.output_validator import OutputValidator, OutputValidationError
from tactus.core.execution_context import BaseExecutionContext
from tactus.core.exceptions import ProcedureWaitingForHuman, TactusRuntimeError
from tactus.protocols.storage import StorageBackend
from tactus.protocols.hitl import HITLHandler
from tactus.protocols.chat_recorder import ChatRecorder

# For backwards compatibility with YAML
try:
    from tactus.core.yaml_parser import ProcedureYAMLParser, ProcedureConfigError
except ImportError:
    ProcedureYAMLParser = None
    ProcedureConfigError = TactusRuntimeError

# Import primitives
from tactus.primitives.state import StatePrimitive
from tactus.primitives.control import IterationsPrimitive, StopPrimitive
from tactus.primitives.tool import ToolPrimitive
from tactus.primitives.human import HumanPrimitive
from tactus.primitives.step import StepPrimitive, CheckpointPrimitive
from tactus.primitives.log import LogPrimitive
from tactus.primitives.message_history import MessageHistoryPrimitive
from tactus.primitives.json import JsonPrimitive
from tactus.primitives.retry import RetryPrimitive
from tactus.primitives.file import FilePrimitive
from tactus.primitives.procedure import ProcedurePrimitive
from tactus.primitives.system import SystemPrimitive
from tactus.primitives.host import HostPrimitive

logger = logging.getLogger(__name__)


class TactusRuntime:
    """
    Main execution engine for Lua-based workflows.

    Responsibilities:
    - Parse and validate YAML configuration
    - Setup sandboxed Lua environment
    - Create and inject primitives
    - Configure agents with LLMs and tools (if available)
    - Execute Lua workflow code
    - Return results
    """

    def __init__(
        self,
        procedure_id: str,
        storage_backend: StorageBackend | None = None,
        hitl_handler: HITLHandler | None = None,
        chat_recorder: ChatRecorder | None = None,
        mcp_server=None,
        mcp_servers: dict[str, Any] | None = None,
        openai_api_key: str | None = None,
        log_handler=None,
        tool_primitive: ToolPrimitive | None = None,
        recursion_depth: int = 0,
        tool_paths: list[str] | None = None,
        external_config: dict[str, Any] | None = None,
        run_id: str | None = None,
        source_file_path: str | None = None,
    ):
        """
        Initialize the Tactus runtime.

        Args:
            procedure_id: Unique procedure identifier
            storage_backend: Storage backend for checkpoints and state
            hitl_handler: Handler for human-in-the-loop interactions
            chat_recorder: Optional chat recorder for conversation logging
            mcp_server: DEPRECATED - use mcp_servers instead
            mcp_servers: Optional dict of MCP server configs {name: {command, args, env}}
            openai_api_key: Optional OpenAI API key for LLMs
            log_handler: Optional handler for structured log events
            tool_primitive: Optional pre-configured ToolPrimitive (for testing with mocks)
            tool_paths: Optional list of paths to scan for local Python tool plugins
            external_config: Optional external config (from .tac.yml) to merge with DSL config
            run_id: Optional run identifier for tagging checkpoints
            source_file_path: Optional path to the .tac file being executed (for accurate source locations)
        """
        self.procedure_id = procedure_id
        self.storage_backend = storage_backend

        # Initialize HITL handler - use new ControlLoopHandler by default
        if hitl_handler is None:
            # Auto-configure control loop with channels
            from tactus.adapters.channels import load_default_channels
            from tactus.adapters.control_loop import ControlLoopHandler, ControlLoopHITLAdapter

            channels = load_default_channels(procedure_id=procedure_id)
            if channels:
                control_handler = ControlLoopHandler(
                    channels=channels,
                    storage=storage_backend,
                )
                # Wrap in adapter for HITLHandler compatibility
                self.hitl_handler = ControlLoopHITLAdapter(control_handler)
                logger.info(
                    "Auto-configured ControlLoopHandler with %s channel(s)",
                    len(channels),
                )
            else:
                # No channels available, leave hitl_handler as None
                self.hitl_handler = None
                logger.warning(
                    "No control channels available - HITL interactions will use defaults"
                )
        else:
            self.hitl_handler = hitl_handler

        self.chat_recorder = chat_recorder
        self.mcp_server = mcp_server  # Keep for backward compatibility
        self.mcp_servers = mcp_servers or {}
        self.mcp_manager = None  # Will be initialized in _setup_agents
        self.openai_api_key = openai_api_key
        self.log_handler = log_handler
        self._injected_tool_primitive = tool_primitive
        self.tool_paths = tool_paths or []
        self.recursion_depth = recursion_depth
        self.external_config = external_config or {}
        self.run_id = run_id
        self.source_file_path = source_file_path

        # Will be initialized during setup
        self.config: dict[str, Any] | None = None  # Legacy YAML support
        self.registry: ProcedureRegistry | None = None  # New DSL registry
        self.lua_sandbox: LuaSandbox | None = None
        self.output_validator: OutputValidator | None = None
        self.template_resolver: TemplateResolver | None = None
        self.message_history_manager: MessageHistoryManager | None = None

        # Execution context
        self.execution_context: BaseExecutionContext | None = None

        # Primitives (shared across all agents)
        self.state_primitive: StatePrimitive | None = None
        self.iterations_primitive: IterationsPrimitive | None = None
        self.stop_primitive: StopPrimitive | None = None
        self.tool_primitive: ToolPrimitive | None = None
        self.human_primitive: HumanPrimitive | None = None
        self.step_primitive: StepPrimitive | None = None
        self.checkpoint_primitive: CheckpointPrimitive | None = None
        self.log_primitive: LogPrimitive | None = None
        self.json_primitive: JsonPrimitive | None = None
        self.retry_primitive: RetryPrimitive | None = None
        self.file_primitive: FilePrimitive | None = None
        self.procedure_primitive: ProcedurePrimitive | None = None
        self.system_primitive: SystemPrimitive | None = None
        self.host_primitive: HostPrimitive | None = None

        # Agent primitives (one per agent)
        self.agents: dict[str, Any] = {}

        # Model primitives (one per model)
        self.models: dict[str, Any] = {}

        # Toolset registry (name -> AbstractToolset instance)
        self.toolset_registry: dict[str, Any] = {}

        # User dependencies (HTTP clients, DB connections, etc.)
        self.user_dependencies: dict[str, Any] = {}
        self.dependency_manager: Any | None = None  # ResourceManager for cleanup

        # Mock manager for testing
        self.mock_manager: Any | None = None  # MockManager instance
        self.external_agent_mocks: dict[str, list[dict[str, Any]]] | None = None
        self.mock_all_agents: bool = False

        logger.info("TactusRuntime initialized for procedure %s", procedure_id)

    async def execute(
        self, source: str, context: dict[str, Any] | None = None, format: str = "yaml"
    ) -> dict[str, Any]:
        """
        Execute a workflow (Lua DSL or legacy YAML format).

        Args:
            source: Lua DSL source code (.tac) or YAML config (legacy)
            context: Optional context dict with pre-loaded data (can override params)
            format: Source format - "lua" (default) or "yaml" (legacy)

        Returns:
            Execution results dict with:
                - success: bool
                - result: Any (return value from Lua workflow)
                - state: Final state
                - iterations: Number of iterations
                - tools_used: List of tool names called
                - error: Error message if failed

        Raises:
            TactusRuntimeError: If execution fails
        """
        chat_session_id = None
        self.context = context or {}  # Store context for param merging

        try:
            # 0. Setup Lua sandbox FIRST (needed for both YAML and Lua DSL)
            logger.info("Step 0: Setting up Lua sandbox")
            strict_determinism = self.external_config.get("strict_determinism", False)

            # Compute base_path for sandbox from source file path if available
            # This ensures require() works correctly even when running from different directories
            sandbox_base_path = None
            if self.source_file_path:
                from pathlib import Path

                sandbox_base_path = str(Path(self.source_file_path).parent.resolve())
                logger.debug(
                    "Using source file directory as sandbox base_path: %s",
                    sandbox_base_path,
                )

            self.lua_sandbox = LuaSandbox(
                execution_context=None,
                strict_determinism=strict_determinism,
                base_path=sandbox_base_path,
            )

            # 0.5. Create execution context EARLY so it's available during DSL parsing
            # This is critical for immediate agent creation during parsing
            logger.info("Step 0.5: Creating execution context (early)")
            self.execution_context = BaseExecutionContext(
                procedure_id=self.procedure_id,
                storage_backend=self.storage_backend,
                hitl_handler=self.hitl_handler,
                strict_determinism=strict_determinism,
                log_handler=self.log_handler,
            )

            # Set run_id if provided
            if self.run_id:
                self.execution_context.set_run_id(self.run_id)
            logger.debug(
                "[CHECKPOINT] BaseExecutionContext created early for immediate agent creation"
            )

            # Attach execution context to sandbox for determinism checking (bidirectional)
            self.lua_sandbox.set_execution_context(self.execution_context)
            # Also store lua_sandbox reference on execution_context for debug.getinfo access
            self.execution_context.set_lua_sandbox(self.lua_sandbox)
            logger.debug("[CHECKPOINT] ExecutionContext and LuaSandbox connected bidirectionally")

            # Set .tac file path NOW (before parsing) so source location is available during agent calls
            if self.source_file_path:
                self.execution_context.set_tac_file(self.source_file_path, source)
                logger.info("[CHECKPOINT] Set .tac file path EARLY: %s", self.source_file_path)
            else:
                logger.warning("[CHECKPOINT] .tac file path NOT set - source_file_path is None")

            # 0b. For Lua DSL, inject placeholder primitives BEFORE parsing
            # so they're available in the procedure function's closure
            placeholder_tool_primitive = None  # Will be set for Lua DSL
            if format == "lua":
                logger.debug("Pre-injecting placeholder primitives for Lua DSL parsing")
                # Import here to avoid issues with YAML format
                from tactus.primitives.log import LogPrimitive as LuaLogPrimitive
                from tactus.primitives.state import StatePrimitive as LuaStatePrimitive
                from tactus.primitives.tool import ToolPrimitive as LuaToolPrimitive
                from tactus.primitives.system import SystemPrimitive as LuaSystemPrimitive

                # Create minimal primitives that don't need full config
                placeholder_log = LuaLogPrimitive(procedure_id=self.procedure_id)
                placeholder_state = LuaStatePrimitive()
                # Use injected tool primitive if provided (for mock mode)
                # This ensures ToolHandles (like done) use the same primitive as MockAgentPrimitive
                if self._injected_tool_primitive:
                    placeholder_tool_primitive = self._injected_tool_primitive
                    logger.debug("Using injected tool primitive for parsing (mock mode)")
                else:
                    # Create tool primitive with log_handler so direct tool calls are tracked
                    placeholder_tool_primitive = LuaToolPrimitive(
                        log_handler=self.log_handler, procedure_id=self.procedure_id
                    )
                placeholder_params = {}  # Empty params dict
                self.lua_sandbox.inject_primitive("Log", placeholder_log)
                # Inject _state_primitive for metatable to use
                self.lua_sandbox.inject_primitive("_state_primitive", placeholder_state)

                # Create State object with special methods and lowercase state proxy with metatable
                self.lua_sandbox.lua.execute(
                    """
                    State = {
                        increment = function(key, amount)
                            return _state_primitive.increment(key, amount or 1)
                        end,
                        append = function(key, value)
                            return _state_primitive.append(key, value)
                        end,
                        all = function()
                            return _state_primitive.all()
                        end
                    }

                    -- Create lowercase 'state' proxy with metatable
                    state = setmetatable({}, {
                        __index = function(_, key)
                            return _state_primitive.get(key)
                        end,
                        __newindex = function(_, key, value)
                            _state_primitive.set(key, value)
                        end
                    })
                """
                )
                self.lua_sandbox.inject_primitive("Tool", placeholder_tool_primitive)
                self.lua_sandbox.inject_primitive("params", placeholder_params)
                placeholder_system = LuaSystemPrimitive(
                    procedure_id=self.procedure_id, log_handler=self.log_handler
                )
                self.lua_sandbox.inject_primitive("System", placeholder_system)

            # 1. Parse configuration (Lua DSL or YAML)
            if format == "lua":
                logger.info("Step 1: Parsing Lua DSL configuration")

                # Script mode: wrap top-level executable code in an implicit main Procedure
                # so agents/tools aren't executed during parsing.
                source = self._maybe_transform_script_mode_source(source)

                # Pass placeholder_tool so tool() can return callable ToolHandles
                self.registry = self._parse_declarations(source, placeholder_tool_primitive)
                logger.info("Loaded procedure from Lua DSL")
                # Convert registry to config dict for compatibility
                self.config = self._registry_to_config(self.registry)
                logger.debug(
                    "Registry contents: agents=%s, lua_tools=%s",
                    list(self.registry.agents.keys()),
                    list(self.registry.lua_tools.keys()),
                )

                # Process mocks from registry if mock_manager exists
                if self.mock_manager and self.registry.mocks:
                    logger.info(f"Registering {len(self.registry.mocks)} mocks from DSL")
                    for tool_name, mock_config in self.registry.mocks.items():
                        self.mock_manager.register_mock(tool_name, mock_config)
                        self.mock_manager.enable_mock(tool_name)
                        logger.debug(f"Registered and enabled mock for tool '{tool_name}'")

                # Apply external, per-scenario agent mocks (from BDD steps).
                # These should take precedence over any `Mocks { ... }` declared in the .tac file.
                if self.external_agent_mocks and self.registry:
                    from tactus.core.registry import AgentMockConfig

                    for agent_name, temporal_turns in self.external_agent_mocks.items():
                        if not isinstance(temporal_turns, list):
                            raise TactusRuntimeError(
                                f"External agent mocks for '{agent_name}' must be a list of turns"
                            )
                        self.registry.agent_mocks[agent_name] = AgentMockConfig(
                            temporal=temporal_turns
                        )

                # If we're in mocked mode, ensure agents are mocked deterministically even if
                # the .tac file doesn't declare `Mocks { ... }` for them.
                if self.mock_all_agents and self.registry:
                    from tactus.core.registry import AgentMockConfig

                    for agent_name in self.registry.agents.keys():
                        if agent_name not in self.registry.agent_mocks:
                            self.registry.agent_mocks[agent_name] = AgentMockConfig(
                                message=f"Mocked response from {agent_name}"
                            )

                # Merge external config (from .tac.yml) into self.config
                # External config provides toolsets, default_toolsets, etc.
                if self.external_config:
                    # Merge toolsets from external config
                    if "toolsets" in self.external_config:
                        if "toolsets" not in self.config:
                            self.config["toolsets"] = {}
                        self.config["toolsets"].update(self.external_config["toolsets"])

                    # Merge other external config keys (like default_toolsets)
                    for key in ["default_toolsets", "default_model", "default_provider"]:
                        if key in self.external_config:
                            self.config[key] = self.external_config[key]

                    logger.debug("Merged external config with %s keys", len(self.external_config))
            else:
                # Legacy YAML support
                logger.info("Step 1: Parsing YAML configuration (legacy)")
                if ProcedureYAMLParser is None:
                    raise TactusRuntimeError("YAML support not available - use Lua DSL format")
                self.config = ProcedureYAMLParser.parse(source)
                logger.info(
                    "Loaded procedure: %s v%s",
                    self.config["name"],
                    self.config["version"],
                )

            # 2. Setup output validator
            logger.info("Step 2: Setting up output validator")
            output_schema = self.config.get("output", {})
            self.output_validator = OutputValidator(output_schema)
            if output_schema:
                logger.info(
                    "Output schema has %s fields: %s",
                    len(output_schema),
                    list(output_schema.keys()),
                )

            # 3. Lua sandbox is already set up in step 0
            # (keeping this comment for step numbering consistency)

            # 4. Initialize primitives
            logger.info("Step 4: Initializing primitives")
            # Pass placeholder_tool so direct tool calls are tracked in the same primitive
            await self._initialize_primitives(placeholder_tool=placeholder_tool_primitive)

            # 4b. Initialize template resolver and session manager
            self.template_resolver = TemplateResolver(
                params=context or {},
                state={},  # Will be updated dynamically
            )
            self.message_history_manager = MessageHistoryManager()
            logger.debug("Template resolver and message history manager initialized")

            # 5. Start chat session if recorder available
            if self.chat_recorder:
                logger.info("Step 5: Starting chat session")
                chat_session_id = await self.chat_recorder.start_session(context)
                if chat_session_id:
                    logger.info("Chat session started: %s", chat_session_id)
                else:
                    logger.warning("Failed to create chat session - continuing without recording")

            # 6. Execution context already created in Step 0.5
            # (.tac file path and lua_sandbox reference already set in Step 0.5)
            logger.info("Step 6: Execution context configuration (already done in Step 0.5)")

            # 7. Initialize HITL and checkpoint primitives (require execution_context)
            logger.info("Step 7: Initializing HITL and checkpoint primitives")
            hitl_config = self.config.get("hitl", {})
            self.human_primitive = HumanPrimitive(self.execution_context, hitl_config)
            self.step_primitive = StepPrimitive(self.execution_context)
            self.checkpoint_primitive = CheckpointPrimitive(self.execution_context)
            self.log_primitive = LogPrimitive(
                procedure_id=self.procedure_id, log_handler=self.log_handler
            )
            self.message_history_primitive = MessageHistoryPrimitive(
                message_history_manager=self.message_history_manager
            )
            self.json_primitive = JsonPrimitive(lua_sandbox=self.lua_sandbox)
            self.retry_primitive = RetryPrimitive()
            self.file_primitive = FilePrimitive(execution_context=self.execution_context)
            self.system_primitive = SystemPrimitive(
                procedure_id=self.procedure_id, log_handler=self.log_handler
            )
            self.host_primitive = HostPrimitive()

            # Initialize Procedure primitive (requires execution_context)
            max_depth = self.config.get("max_depth", 5) if self.config else 5
            self.procedure_primitive = ProcedurePrimitive(
                execution_context=self.execution_context,
                runtime_factory=self._create_runtime_for_procedure,
                lua_sandbox=self.lua_sandbox,
                max_depth=max_depth,
                current_depth=self.recursion_depth,
            )
            logger.debug("HITL, checkpoint, message history, and procedure primitives initialized")

            # 7.5. Initialize toolset registry
            logger.info("Step 7.5: Initializing toolset registry")
            await self._initialize_toolsets()

            # 7.6. Initialize named procedure callables
            logger.info("Step 7.6: Initializing named procedure callables")
            await self._initialize_named_procedures()

            # 8. Setup agents with LLMs and tools
            logger.info("Step 8: Setting up agents")
            # Set OpenAI API key in environment if provided (for OpenAI agents)
            import os

            if self.openai_api_key and "OPENAI_API_KEY" not in os.environ:
                os.environ["OPENAI_API_KEY"] = self.openai_api_key

            # Always set up agents - they may use providers other than OpenAI (e.g., Bedrock)
            await self._setup_agents(context or {})

            # Setup models for ML inference
            await self._setup_models()

            # 9. Inject primitives into Lua
            logger.info("Step 9: Injecting primitives into Lua environment")
            self._inject_primitives()

            # 10. Execute workflow (may raise ProcedureWaitingForHuman)
            logger.info("Step 10: Executing Lua workflow")
            workflow_result = self._execute_workflow()

            # 10.5. Apply return_prompt if specified (future: inject to agent for summary)
            if self.config.get("return_prompt"):
                return_prompt = self.config["return_prompt"]
                logger.info("Return prompt specified: %s...", return_prompt[:50])
                # TODO: In full implementation, inject this prompt to an agent to get a summary
                # For now, just log it

            # 11. Validate workflow output
            logger.info("Step 11: Validating workflow output")
            try:
                validated_result = self.output_validator.validate(workflow_result)
                logger.info("✓ Output validation passed")
            except OutputValidationError as e:
                logger.error(f"Output validation failed: {e}")
                # Still continue but mark as validation failure
                validated_result = workflow_result

            # 12. Flush all queued chat recordings
            if self.chat_recorder:
                logger.info("Step 12: Flushing chat recordings")
                # Flush agent messages if agents have flush capability
                for agent_name, agent_primitive in self.agents.items():
                    if hasattr(agent_primitive, "flush_recordings"):
                        await agent_primitive.flush_recordings()

            # 13. End chat session
            if self.chat_recorder and chat_session_id:
                await self.chat_recorder.end_session(chat_session_id, status="COMPLETED")

            # 14. Build final results
            final_state = self.state_primitive.all() if self.state_primitive else {}
            tools_used = (
                [call.name for call in self.tool_primitive.get_all_calls()]
                if self.tool_primitive
                else []
            )

            logger.info(
                "Workflow execution complete: %s iterations, %s tool calls",
                self.iterations_primitive.current() if self.iterations_primitive else 0,
                len(tools_used),
            )

            # Collect cost events and calculate totals
            cost_breakdown = []
            total_cost = 0.0
            total_tokens = 0

            if self.log_handler and hasattr(self.log_handler, "cost_events"):
                # Get cost events from log handler
                cost_breakdown = self.log_handler.cost_events
                for event in cost_breakdown:
                    total_cost += event.total_cost
                    total_tokens += event.total_tokens

            # Send execution summary event if log handler is available
            if self.log_handler:
                from tactus.protocols.models import ExecutionSummaryEvent

                # Compute checkpoint metrics from execution log
                checkpoint_count = 0
                checkpoint_types = {}
                checkpoint_duration_ms = 0.0

                if self.execution_context and hasattr(self.execution_context, "metadata"):
                    checkpoints = self.execution_context.metadata.execution_log
                    checkpoint_count = len(checkpoints)

                    for checkpoint in checkpoints:
                        # Count by type
                        checkpoint_type = checkpoint.type
                        checkpoint_types[checkpoint_type] = (
                            checkpoint_types.get(checkpoint_type, 0) + 1
                        )

                        # Sum durations
                        if checkpoint.duration_ms:
                            checkpoint_duration_ms += checkpoint.duration_ms

                summary_event = ExecutionSummaryEvent(
                    result=validated_result,
                    final_state=final_state,
                    iterations=(
                        self.iterations_primitive.current() if self.iterations_primitive else 0
                    ),
                    tools_used=tools_used,
                    procedure_id=self.procedure_id,
                    total_cost=total_cost,
                    total_tokens=total_tokens,
                    cost_breakdown=cost_breakdown,
                    checkpoint_count=checkpoint_count,
                    checkpoint_types=checkpoint_types,
                    checkpoint_duration_ms=(
                        checkpoint_duration_ms if checkpoint_duration_ms > 0 else None
                    ),
                    exit_code=0,  # Success
                )
                self.log_handler.log(summary_event)

            return {
                "success": True,
                "procedure_id": self.procedure_id,
                "result": validated_result,
                "state": final_state,
                "iterations": (
                    self.iterations_primitive.current() if self.iterations_primitive else 0
                ),
                "tools_used": tools_used,
                "stop_requested": self.stop_primitive.requested() if self.stop_primitive else False,
                "stop_reason": self.stop_primitive.reason() if self.stop_primitive else None,
                "session_id": chat_session_id,
                "total_cost": total_cost,
                "total_tokens": total_tokens,
                "cost_breakdown": cost_breakdown,
            }

        except ProcedureWaitingForHuman as e:
            logger.info("Procedure waiting for human: %s", e)

            # Flush recordings before exiting
            if self.chat_recorder:
                for agent_primitive in self.agents.values():
                    if hasattr(agent_primitive, "flush_recordings"):
                        await agent_primitive.flush_recordings()

            # Note: Procedure status updated by execution context
            # Chat session stays active for resume

            return {
                "success": False,
                "status": "WAITING_FOR_HUMAN",
                "procedure_id": self.procedure_id,
                "pending_message_id": getattr(e, "pending_message_id", None),
                "message": str(e),
                "session_id": chat_session_id,
            }

        except ProcedureConfigError as e:
            logger.error("Configuration error: %s", e)
            # Flush recordings even on error
            if self.chat_recorder and chat_session_id:
                try:
                    await self.chat_recorder.end_session(chat_session_id, status="FAILED")
                except Exception as err:
                    logger.warning("Failed to end chat session: %s", err)

            # Send error summary event if log handler is available
            if self.log_handler:
                import traceback
                from tactus.protocols.models import ExecutionSummaryEvent

                summary_event = ExecutionSummaryEvent(
                    result=None,
                    final_state={},
                    iterations=0,
                    tools_used=[],
                    procedure_id=self.procedure_id,
                    total_cost=0.0,
                    total_tokens=0,
                    cost_breakdown=[],
                    exit_code=1,
                    error_message=str(e),
                    error_type=type(e).__name__,
                    traceback=traceback.format_exc(),
                )
                self.log_handler.log(summary_event)

            return {
                "success": False,
                "procedure_id": self.procedure_id,
                "error": f"Configuration error: {e}",
            }

        except LuaSandboxError as e:
            logger.error("Lua execution error: %s", e)

            # Apply error_prompt if specified (future: inject to agent for explanation)
            if self.config and self.config.get("error_prompt"):
                error_prompt = self.config["error_prompt"]
                logger.info("Error prompt specified: %s...", error_prompt[:50])
                # TODO: In full implementation, inject this prompt to an agent to get an explanation

            # Flush recordings even on error
            if self.chat_recorder and chat_session_id:
                try:
                    await self.chat_recorder.end_session(chat_session_id, status="FAILED")
                except Exception as err:
                    logger.warning("Failed to end chat session: %s", err)

            # Send error summary event if log handler is available
            if self.log_handler:
                import traceback
                from tactus.protocols.models import ExecutionSummaryEvent

                summary_event = ExecutionSummaryEvent(
                    result=None,
                    final_state={},
                    iterations=0,
                    tools_used=[],
                    procedure_id=self.procedure_id,
                    total_cost=0.0,
                    total_tokens=0,
                    cost_breakdown=[],
                    exit_code=1,
                    error_message=str(e),
                    error_type=type(e).__name__,
                    traceback=traceback.format_exc(),
                )
                self.log_handler.log(summary_event)

            return {
                "success": False,
                "procedure_id": self.procedure_id,
                "error": f"Lua execution error: {e}",
            }

        except Exception as e:
            logger.error("Unexpected error: %s", e, exc_info=True)

            # Apply error_prompt if specified (future: inject to agent for explanation)
            if self.config and self.config.get("error_prompt"):
                error_prompt = self.config["error_prompt"]
                logger.info("Error prompt specified: %s...", error_prompt[:50])
                # TODO: In full implementation, inject this prompt to an agent to get an explanation

            # Flush recordings even on error
            if self.chat_recorder and chat_session_id:
                try:
                    await self.chat_recorder.end_session(chat_session_id, status="FAILED")
                except Exception as err:
                    logger.warning("Failed to end chat session: %s", err)

            # Send error summary event if log handler is available
            if self.log_handler:
                import traceback
                from tactus.protocols.models import ExecutionSummaryEvent

                summary_event = ExecutionSummaryEvent(
                    result=None,
                    final_state={},
                    iterations=0,
                    tools_used=[],
                    procedure_id=self.procedure_id,
                    total_cost=0.0,
                    total_tokens=0,
                    cost_breakdown=[],
                    exit_code=1,
                    error_message=str(e),
                    error_type=type(e).__name__,
                    traceback=traceback.format_exc(),
                )
                self.log_handler.log(summary_event)

            return {
                "success": False,
                "procedure_id": self.procedure_id,
                "error": f"Unexpected error: {e}",
            }

        finally:
            # Cleanup: Disconnect from MCP servers
            if self.mcp_manager:
                try:
                    await self.mcp_manager.__aexit__(None, None, None)
                    logger.info("Disconnected from MCP servers")
                except Exception as e:
                    logger.warning("Error disconnecting from MCP servers: %s", e)

            # Cleanup: Close user dependencies
            if self.dependency_manager:
                try:
                    await self.dependency_manager.cleanup()
                    logger.info("Cleaned up user dependencies")
                except Exception as e:
                    logger.warning("Error cleaning up dependencies: %s", e)

    async def _initialize_primitives(
        self,
        placeholder_tool: ToolPrimitive | None = None,
    ):
        """Initialize all primitive objects.

        Args:
            placeholder_tool: Optional ToolPrimitive created during DSL parsing.
                              If provided, it will be reused to preserve direct tool
                              call tracking from ToolHandles.
        """
        # Get state schema from registry if available
        state_schema = self.registry.state_schema if self.registry else {}
        self.state_primitive = StatePrimitive(state_schema=state_schema)
        self.iterations_primitive = IterationsPrimitive()
        self.stop_primitive = StopPrimitive()

        # Use injected tool primitive if provided (for testing with mocks)
        if self._injected_tool_primitive:
            self.tool_primitive = self._injected_tool_primitive
            logger.info("Using injected tool primitive (mock mode)")
        elif placeholder_tool:
            # Reuse placeholder tool primitive so direct tool calls from ToolHandles are tracked
            self.tool_primitive = placeholder_tool
            logger.debug("Reusing placeholder tool primitive for direct tool call tracking")
        else:
            self.tool_primitive = ToolPrimitive(
                log_handler=self.log_handler, procedure_id=self.procedure_id
            )

        # Connect tool primitive to runtime for Tool.get() support
        self.tool_primitive.set_runtime(self)

        # Initialize toolset primitive (needs runtime reference for resolution)
        from tactus.primitives.toolset import ToolsetPrimitive

        self.toolset_primitive = ToolsetPrimitive(runtime=self)

        logger.debug("All primitives initialized")

    def resolve_toolset(self, name: str) -> Any | None:
        """
        Resolve a toolset by name from runtime's registered toolsets.

        This is called by ToolsetPrimitive.get() and agent setup to look up toolsets.

        Args:
            name: Toolset name to resolve

        Returns:
            AbstractToolset instance or None if not found
        """
        toolset = self.toolset_registry.get(name)
        if toolset:
            logger.debug(f"Resolved toolset '{name}' from registry")
            return toolset
        else:
            logger.warning(
                f"Toolset '{name}' not found in registry. Available: {list(self.toolset_registry.keys())}"
            )
            return None

    async def _initialize_toolsets(self):
        """
        Load and register all toolsets from config and DSL-defined sources.

        This method:
        1. Loads config-defined toolsets from YAML
        2. Registers MCP toolsets by server name
        3. Registers plugin toolset if tool_paths configured
        4. Registers DSL-defined toolsets (from tool() declarations)

        Note: There are no built-in toolsets. Programmers must define their own
        tools using tool() declarations in their .tac files.
        """
        logger.info(
            f"Starting _initialize_toolsets, registry has {len(self.registry.lua_tools) if self.registry else 0} lua_tools"
        )

        # 1. Load config-defined toolsets
        config_toolsets = self.config.get("toolsets", {})
        for name, definition in config_toolsets.items():
            try:
                toolset = await self._create_toolset_from_config(name, definition)
                if toolset:
                    self.toolset_registry[name] = toolset
                    logger.info(f"Registered config-defined toolset '{name}'")
            except Exception as e:
                logger.error(f"Failed to create toolset '{name}' from config: {e}", exc_info=True)

        # 3. Register MCP toolsets by server name
        if self.mcp_servers:
            try:
                from tactus.adapters.mcp_manager import MCPServerManager

                self.mcp_manager = MCPServerManager(
                    self.mcp_servers, tool_primitive=self.tool_primitive
                )
                await self.mcp_manager.__aenter__()

                # Register each MCP toolset by server name
                for server_name in self.mcp_servers.keys():
                    # Get the toolset for this specific server
                    toolset = self.mcp_manager.get_toolset_by_name(server_name)
                    if toolset:
                        self.toolset_registry[server_name] = toolset
                        logger.info(f"Registered MCP toolset '{server_name}'")

                # Get all toolsets for logging
                mcp_toolsets = self.mcp_manager.get_toolsets()
                logger.info(f"Connected to {len(mcp_toolsets)} MCP server(s)")
            except Exception as e:
                # Check if this is a fileno error (common in test environments with redirected stderr)
                error_str = str(e)
                if "fileno" in error_str or isinstance(e, io.UnsupportedOperation):
                    logger.warning(
                        "MCP server initialization skipped (test environment with redirected streams)"
                    )
                else:
                    logger.error(f"Failed to initialize MCP toolsets: {e}", exc_info=True)

        # 4. Register plugin toolset if tool_paths configured
        if self.tool_paths:
            try:
                from tactus.adapters.plugins import PluginLoader

                plugin_loader = PluginLoader(tool_primitive=self.tool_primitive)
                plugin_toolset = plugin_loader.create_toolset(self.tool_paths, name="plugin")
                self.toolset_registry["plugin"] = plugin_toolset
                logger.info(f"Registered plugin toolset from {len(self.tool_paths)} path(s)")
            except ImportError as e:
                logger.warning(
                    f"Could not import PluginLoader: {e} - local tools will not be available"
                )
            except Exception as e:
                logger.error(f"Failed to create plugin toolset: {e}", exc_info=True)

        # 5. Register individual Lua tool() declarations BEFORE toolsets that reference them
        logger.info(
            f"Checking for Lua tools: has registry={hasattr(self, 'registry')}, registry not None={self.registry is not None if hasattr(self, 'registry') else False}"
        )
        if hasattr(self, "registry") and self.registry and hasattr(self.registry, "lua_tools"):
            logger.info(f"Found {len(self.registry.lua_tools)} Lua tools to register")
            try:
                from tactus.adapters.lua_tools import LuaToolsAdapter

                lua_adapter = LuaToolsAdapter(
                    tool_primitive=self.tool_primitive, mock_manager=self.mock_manager
                )

                for tool_name, tool_spec in self.registry.lua_tools.items():
                    try:
                        # Check if this tool references an external source
                        source = tool_spec.get("source")
                        logger.info(
                            f"Processing Lua tool '{tool_name}': source={source}, spec keys={list(tool_spec.keys())}"
                        )
                        if source:
                            # Resolve the external tool
                            resolved_tool = await self._resolve_tool_source(tool_name, source)
                            if resolved_tool:
                                self.toolset_registry[tool_name] = resolved_tool
                                logger.info(f"Registered tool '{tool_name}' from source '{source}'")
                                # Debug: print the actual tool
                                logger.debug(f"Tool object: {resolved_tool}")
                            else:
                                logger.error(
                                    f"Failed to resolve tool '{tool_name}' from source '{source}'"
                                )
                        else:
                            # Regular inline Lua tool
                            toolset = lua_adapter.create_single_tool_toolset(tool_name, tool_spec)
                            self.toolset_registry[tool_name] = toolset
                            logger.info(f"Registered Lua tool '{tool_name}' as toolset")
                    except Exception as e:
                        logger.error(f"Failed to create Lua tool '{tool_name}': {e}", exc_info=True)
            except ImportError as e:
                logger.warning(
                    f"Could not import LuaToolsAdapter: {e} - Lua tools will not be available"
                )

        # 6. Register DSL-defined toolsets from registry (after individual tools are registered)
        # DEBUG: Write to stderr which should show up in logs
        import sys

        sys.stderr.write("\n\n===  DSL TOOLSET REGISTRATION START ===\n")
        sys.stderr.write(f"Has registry: {hasattr(self, 'registry')}\n")
        if hasattr(self, "registry") and self.registry:
            sys.stderr.write("Registry is not None: True\n")
            sys.stderr.write(f"Registry has toolsets attr: {hasattr(self.registry, 'toolsets')}\n")
            if hasattr(self.registry, "toolsets"):
                sys.stderr.write(f"Registry toolsets: {list(self.registry.toolsets.keys())}\n")
                sys.stderr.write(f"Registry toolsets count: {len(self.registry.toolsets)}\n")
        else:
            sys.stderr.write("Registry is None or doesn't exist\n")
        sys.stderr.flush()

        logger.info("=== DSL TOOLSET REGISTRATION START ===")
        logger.info(f"Has registry: {hasattr(self, 'registry')}")
        logger.info(
            f"Registry is not None: {self.registry is not None if hasattr(self, 'registry') else False}"
        )
        if hasattr(self, "registry") and self.registry:
            logger.info(f"Registry has toolsets attr: {hasattr(self.registry, 'toolsets')}")
            if hasattr(self.registry, "toolsets"):
                logger.info(f"Registry toolsets: {list(self.registry.toolsets.keys())}")
                logger.info(f"Registry toolsets count: {len(self.registry.toolsets)}")

        if hasattr(self, "registry") and self.registry and hasattr(self.registry, "toolsets"):
            sys.stderr.write(f"Processing {len(self.registry.toolsets)} DSL toolsets\n")
            sys.stderr.flush()
            logger.info(f"Processing {len(self.registry.toolsets)} DSL toolsets")
            for name, definition in self.registry.toolsets.items():
                sys.stderr.write(
                    f"Creating DSL toolset '{name}' with config keys: {list(definition.keys())}\n"
                )
                sys.stderr.flush()
                logger.info(
                    f"Creating DSL toolset '{name}' with config keys: {list(definition.keys())}"
                )
                try:
                    toolset = await self._create_toolset_from_config(name, definition)
                    if toolset:
                        self.toolset_registry[name] = toolset
                        sys.stderr.write(f"✓ Registered DSL-defined toolset '{name}'\n")
                        sys.stderr.flush()
                        logger.info(f"✓ Registered DSL-defined toolset '{name}'")
                    else:
                        sys.stderr.write(f"✗ Toolset '{name}' creation returned None\n")
                        sys.stderr.flush()
                        logger.error(f"✗ Toolset '{name}' creation returned None")
                except Exception as e:
                    sys.stderr.write(f"✗ Failed to create DSL toolset '{name}': {e}\n")
                    sys.stderr.flush()
                    logger.error(f"✗ Failed to create DSL toolset '{name}': {e}", exc_info=True)
        else:
            sys.stderr.write("No DSL toolsets to register (registry.toolsets not available)\n")
            sys.stderr.flush()
            logger.warning("No DSL toolsets to register (registry.toolsets not available)")
        sys.stderr.write("=== DSL TOOLSET REGISTRATION END ===\n")
        sys.stderr.flush()
        logger.info("=== DSL TOOLSET REGISTRATION END ===")

        logger.info(
            f"Toolset registry initialized with {len(self.toolset_registry)} toolset(s): {list(self.toolset_registry.keys())}"
        )

        # Debug: Print what's in the toolset registry
        for name, toolset in self.toolset_registry.items():
            logger.debug(f"  - {name}: {type(toolset)} -> {toolset}")

    async def _resolve_tool_source(self, tool_name: str, source: str) -> Any | None:
        """
        Resolve a tool from an external source.

        Args:
            tool_name: Name of the tool
            source: Source identifier (e.g., "./file.tac", "mcp.server")

        Returns:
            Toolset containing the resolved tool, or None if not found

        Note:
            Standard library tools (tactus.tools.*) should be loaded via require()
            in the .tac file, not via this method.
        """
        # Handle local .tac file imports (./path/file.tac)
        if source.startswith("./") or source.startswith("/"):
            from pathlib import Path

            # Resolve path relative to the source file if available
            if self.source_file_path and source.startswith("./"):
                base_dir = Path(self.source_file_path).parent
                file_path = base_dir / source[2:]  # Remove "./" prefix
            else:
                file_path = Path(source)

            # Check if file exists
            if not file_path.exists():
                logger.error(f"Tool source file not found: {file_path}")
                return None

            if not file_path.suffix == ".tac":
                logger.error(f"Tool source must be a .tac file: {file_path}")
                return None

            try:
                # Read and parse the .tac file
                with open(file_path, "r") as f:
                    content = f.read()

                # Create a sub-runtime to load the tools from the file
                # We'll parse the file and extract tool definitions
                # Parse the file content using the DSL
                lua_runtime = self.sandbox.runtime
                lua_runtime.execute(content)

                # Get registered tools from the builder
                # Note: This assumes tools are registered globally during parsing
                # We may need to enhance this to properly isolate tool loading
                logger.info(f"Loaded tools from {file_path}")

                # For now, return None as we need to implement proper tool extraction
                # This will be enhanced in the next iteration
                logger.warning("Tool extraction from .tac files needs enhancement")
                return None

            except Exception as e:
                logger.error(f"Failed to load tools from {file_path}: {e}", exc_info=True)
                return None

        # Handle MCP server tools (mcp.*)
        elif source.startswith("mcp."):
            server_name = source[4:]  # Remove "mcp." prefix
            # Look for the MCP server toolset
            if server_name in self.toolset_registry:
                return self.toolset_registry[server_name]
            else:
                logger.error(f"MCP server '{server_name}' not found in registry")
                return None

        # Handle plugin tools (plugin.*)
        elif source.startswith("plugin."):
            plugin_path = source[7:]  # Remove "plugin." prefix
            try:
                # Split the plugin path into module and function
                path_segments = plugin_path.rsplit(".", 1)
                if len(path_segments) != 2:
                    logger.error(
                        f"Invalid plugin path format: {source} (expected plugin.module.function)"
                    )
                    return None

                module_name, function_name = path_segments

                # Try to import the module
                import importlib

                try:
                    module_object = importlib.import_module(module_name)
                except ModuleNotFoundError:
                    # Try with "tactus.plugins." prefix
                    try:
                        module_object = importlib.import_module(f"tactus.plugins.{module_name}")
                    except ModuleNotFoundError:
                        logger.error(f"Plugin module not found: {module_name}")
                        return None

                # Get the function from the module
                if not hasattr(module_object, function_name):
                    logger.error(
                        "Function '%s' not found in module '%s'",
                        function_name,
                        module_name,
                    )
                    return None

                tool_function = getattr(module_object, function_name)

                # Create a toolset with the plugin tool
                from pydantic_ai.toolsets import FunctionToolset
                from pydantic_ai import Tool

                # Create tracking wrapper
                tool_primitive = self.tool_primitive

                def tracked_plugin_tool(**kwargs):
                    """Wrapper that tracks plugin tool calls."""
                    logger.debug(f"Plugin tool '{tool_name}' called with: {kwargs}")

                    # Check for mock response first
                    if self.mock_manager:
                        mock_result = self.mock_manager.get_mock_response(tool_name, kwargs)
                        if mock_result is not None:
                            logger.debug(f"Using mock response for '{tool_name}': {mock_result}")
                            if tool_primitive:
                                tool_primitive.record_call(tool_name, kwargs, mock_result)
                            if self.mock_manager:
                                self.mock_manager.record_call(tool_name, kwargs, mock_result)
                            return mock_result

                    # Call the plugin function
                    result = tool_function(**kwargs)
                    logger.debug(f"Plugin tool '{tool_name}' returned: {result}")

                    # Track the call
                    if tool_primitive:
                        tool_primitive.record_call(tool_name, kwargs, result)
                    if self.mock_manager:
                        self.mock_manager.record_call(tool_name, kwargs, result)

                    return result

                # Copy metadata
                tracked_plugin_tool.__name__ = tool_name
                tracked_plugin_tool.__doc__ = getattr(
                    tool_function, "__doc__", f"Plugin tool: {tool_name}"
                )

                # Create and return toolset
                wrapped_tool = Tool(tracked_plugin_tool, name=tool_name)
                toolset = FunctionToolset(tools=[wrapped_tool])
                logger.info(
                    "Loaded plugin tool '%s' from %s.%s",
                    tool_name,
                    module_name,
                    function_name,
                )
                return toolset

            except Exception as e:
                logger.error(f"Failed to load plugin tool '{source}': {e}", exc_info=True)
                return None

        # Handle CLI tools (cli.*)
        elif source.startswith("cli."):
            cli_command = source[4:]  # Remove "cli." prefix
            try:
                import subprocess
                import json
                from pydantic_ai.toolsets import FunctionToolset
                from pydantic_ai import Tool

                # Create tracking wrapper
                tool_primitive = self.tool_primitive

                def cli_tool_wrapper(**kwargs):
                    """Wrapper that executes CLI commands."""
                    logger.debug(f"CLI tool '{tool_name}' called with: {kwargs}")

                    # Check for mock response first
                    if self.mock_manager:
                        mock_result = self.mock_manager.get_mock_response(tool_name, kwargs)
                        if mock_result is not None:
                            logger.debug(f"Using mock response for '{tool_name}': {mock_result}")
                            if tool_primitive:
                                tool_primitive.record_call(tool_name, kwargs, mock_result)
                            if self.mock_manager:
                                self.mock_manager.record_call(tool_name, kwargs, mock_result)
                            return mock_result

                    # Build command line
                    command_arguments = [cli_command]

                    # Add arguments from kwargs
                    # Common patterns:
                    # - Boolean flags: {"verbose": True} -> ["--verbose"]
                    # - String args: {"file": "test.txt"} -> ["--file", "test.txt"]
                    # - Positional: {"args": ["arg1", "arg2"]} -> ["arg1", "arg2"]

                    for key, value in kwargs.items():
                        if key == "args" and isinstance(value, list):
                            # Positional arguments
                            command_arguments.extend(value)
                        elif isinstance(value, bool):
                            if value:
                                # Boolean flag
                                flag = f"--{key.replace('_', '-')}"
                                command_arguments.append(flag)
                        elif value is not None:
                            # Key-value argument
                            flag = f"--{key.replace('_', '-')}"
                            command_arguments.extend([flag, str(value)])

                    logger.debug("Executing CLI command: %s", " ".join(command_arguments))

                    try:
                        # Execute the command
                        command_result = subprocess.run(
                            command_arguments,
                            capture_output=True,
                            text=True,
                            check=False,
                            timeout=30,  # 30 second timeout
                        )

                        # Prepare response
                        command_response = {
                            "stdout": command_result.stdout,
                            "stderr": command_result.stderr,
                            "returncode": command_result.returncode,
                            "success": command_result.returncode == 0,
                        }

                        # Try to parse JSON output if possible
                        if command_result.stdout.strip().startswith(
                            "{"
                        ) or command_result.stdout.strip().startswith("["):
                            try:
                                command_response["json"] = json.loads(command_result.stdout)
                            except json.JSONDecodeError:
                                pass

                        logger.debug("CLI tool '%s' returned: %s", tool_name, command_response)

                        # Track the call
                        if tool_primitive:
                            tool_primitive.record_call(tool_name, kwargs, command_response)
                        if self.mock_manager:
                            self.mock_manager.record_call(tool_name, kwargs, command_response)

                        return command_response

                    except subprocess.TimeoutExpired:
                        error_response = {
                            "error": "Command timed out after 30 seconds",
                            "success": False,
                        }
                        if tool_primitive:
                            tool_primitive.record_call(tool_name, kwargs, error_response)
                        return error_response

                    except Exception as e:
                        error_response = {"error": str(e), "success": False}
                        if tool_primitive:
                            tool_primitive.record_call(tool_name, kwargs, error_response)
                        return error_response

                # Set metadata
                cli_tool_wrapper.__name__ = tool_name
                cli_tool_wrapper.__doc__ = f"CLI tool wrapper for: {cli_command}"

                # Create and return toolset
                wrapped_tool = Tool(cli_tool_wrapper, name=tool_name)
                toolset = FunctionToolset(tools=[wrapped_tool])
                logger.info(f"Created CLI tool wrapper for '{cli_command}'")
                return toolset

            except Exception as e:
                logger.error(f"Failed to create CLI tool wrapper '{source}': {e}", exc_info=True)
                return None

        # Handle broker host tools (broker.*)
        elif source.startswith("broker."):
            broker_tool = source[7:]  # Remove "broker." prefix
            if not broker_tool:
                logger.error(
                    f"Invalid broker tool source for '{tool_name}': {source} (expected broker.<tool>)"
                )
                return None

            try:
                from pydantic_ai import Tool
                from pydantic_ai.toolsets import FunctionToolset

                tool_primitive = self.tool_primitive
                host_primitive = self.host_primitive
                mock_manager = self.mock_manager

                def broker_tool_wrapper(**kwargs: Any):
                    if mock_manager:
                        mock_result = mock_manager.get_mock_response(tool_name, kwargs)
                        if mock_result is not None:
                            if tool_primitive:
                                tool_primitive.record_call(tool_name, kwargs, mock_result)
                            mock_manager.record_call(tool_name, kwargs, mock_result)
                            return mock_result

                    result = host_primitive.call(broker_tool, kwargs)

                    if tool_primitive:
                        tool_primitive.record_call(tool_name, kwargs, result)
                    if mock_manager:
                        mock_manager.record_call(tool_name, kwargs, result)

                    return result

                broker_tool_wrapper.__name__ = tool_name
                broker_tool_wrapper.__doc__ = f"Brokered host tool: {broker_tool}"

                wrapped_tool = Tool(broker_tool_wrapper, name=tool_name)
                return FunctionToolset(tools=[wrapped_tool])

            except Exception as e:
                logger.error(
                    f"Failed to create broker tool '{tool_name}' from source '{source}': {e}",
                    exc_info=True,
                )
                return None

        else:
            logger.error(f"Unknown tool source format: {source}")
            return None

    async def _initialize_named_procedures(self):
        """
        Initialize named procedure callables and inject them into Lua sandbox.

        Converts named procedure registrations into ProcedureCallable instances
        that can be called directly from Lua code with automatic checkpointing.
        """
        if not self.registry or not self.registry.named_procedures:
            logger.debug("No named procedures to initialize")
            return

        from tactus.primitives.procedure_callable import ProcedureCallable

        for procedure_name, procedure_definition in self.registry.named_procedures.items():
            try:
                logger.debug(
                    "Processing named procedure '%s': function=%s, type=%s",
                    procedure_name,
                    procedure_definition["function"],
                    type(procedure_definition["function"]),
                )

                # Create callable wrapper
                callable_wrapper = ProcedureCallable(
                    name=procedure_name,
                    procedure_function=procedure_definition["function"],
                    input_schema=procedure_definition["input_schema"],
                    output_schema=procedure_definition["output_schema"],
                    state_schema=procedure_definition["state_schema"],
                    execution_context=self.execution_context,
                    lua_sandbox=self.lua_sandbox,
                )

                # Get the old stub (if it exists) to update its registry
                try:
                    old_value = self.lua_sandbox.lua.globals()[procedure_name]
                    if old_value and hasattr(old_value, "registry"):
                        # Update the stub's registry so it delegates to the real callable
                        old_value.registry[procedure_name] = callable_wrapper
                except (KeyError, AttributeError):
                    # Stub doesn't exist in globals yet, that's fine
                    pass

                # Inject into Lua globals (replaces placeholder)
                self.lua_sandbox.lua.globals()[procedure_name] = callable_wrapper

                logger.info("Registered named procedure: %s", procedure_name)
            except Exception as e:
                logger.error(
                    "Failed to initialize named procedure '%s': %s",
                    procedure_name,
                    e,
                    exc_info=True,
                )

        logger.info(
            "Initialized %s named procedure(s)",
            len(self.registry.named_procedures),
        )

    async def _create_toolset_from_config(
        self, name: str, definition: dict[str, Any]
    ) -> Any | None:
        """
        Create toolset from YAML config definition.

        Supports toolset types:
        - plugin: Load from local Python files
        - lua: Lua function tools
        - mcp: Reference MCP server toolset
        - filtered: Filter tools from source toolset
        - combined: Merge multiple toolsets
        - builtin: Custom built-in toolset

        Args:
            name: Toolset name
            definition: Config dict with 'type' and type-specific fields

        Returns:
            AbstractToolset instance or None if creation fails
        """
        import re
        from pydantic_ai.toolsets import CombinedToolset

        toolset_type = definition.get("type")

        if toolset_type == "lua":
            # Lua function toolset
            try:
                from tactus.adapters.lua_tools import LuaToolsAdapter

                lua_adapter = LuaToolsAdapter(
                    tool_primitive=self.tool_primitive, mock_manager=self.mock_manager
                )
                return lua_adapter.create_lua_toolset(name, definition)
            except ImportError as e:
                logger.error(f"Could not import LuaToolsAdapter: {e}")
                return None

        if toolset_type == "plugin":
            # Load from local paths
            paths = definition.get("paths", [])
            if not paths:
                logger.warning(f"Plugin toolset '{name}' has no paths configured")
                return None

            from tactus.adapters.plugins import PluginLoader

            plugin_loader = PluginLoader(tool_primitive=self.tool_primitive)
            return plugin_loader.create_toolset(paths, name=name)

        elif toolset_type == "mcp":
            # Reference MCP server by name
            server_name = definition.get("server")
            if not server_name:
                logger.error(f"MCP toolset '{name}' missing 'server' field")
                return None

            # Return reference to MCP toolset (will be resolved after MCP init)
            return self.resolve_toolset(server_name)

        elif toolset_type == "filtered":
            # Filter tools from source toolset
            source_name = definition.get("source")
            pattern = definition.get("pattern")

            if not source_name:
                logger.error(f"Filtered toolset '{name}' missing 'source' field")
                return None

            source_toolset = self.resolve_toolset(source_name)
            if not source_toolset:
                logger.error(f"Filtered toolset '{name}' cannot find source '{source_name}'")
                return None

            if pattern:
                # Filter by regex pattern
                return source_toolset.filtered(
                    lambda execution_context, tool: re.match(pattern, tool.name)
                )
            else:
                logger.warning(f"Filtered toolset '{name}' has no filter pattern")
                return source_toolset

        elif toolset_type == "combined":
            # Merge multiple toolsets
            sources = definition.get("sources", [])
            if not sources:
                logger.warning(f"Combined toolset '{name}' has no sources")
                return None

            toolsets = []
            for source_name in sources:
                source = self.resolve_toolset(source_name)
                if source:
                    toolsets.append(source)
                else:
                    logger.warning(f"Combined toolset '{name}' cannot find source '{source_name}'")

            if toolsets:
                return CombinedToolset(toolsets)
            else:
                logger.error(f"Combined toolset '{name}' has no valid sources")
                return None

        elif toolset_type == "builtin":
            # Custom built-in toolset (for future extension)
            logger.warning(f"Builtin toolset type for '{name}' not yet implemented")
            return None

        else:
            # Check if this is a DSL-defined toolset (no explicit type)
            # DSL toolsets can have:
            # - "tools" field with list of tool names or inline tool definitions
            # - "use" field to import from a file or other source
            logger.info(f"[TOOLSET_CREATE] '{name}' has no explicit type, checking for tools/use")

            if "tools" in definition:
                # Handle tools list (can be tool names or inline definitions)
                tools_list = definition["tools"]
                logger.info(
                    f"[TOOLSET_CREATE] '{name}' has tools field with {len(tools_list) if isinstance(tools_list, list) else '?'} items"
                )

                # Check if we have inline tool definitions (dicts with a Lua handler)
                has_inline_tools = False
                if isinstance(tools_list, list):
                    for idx, item in enumerate(tools_list):
                        logger.info(
                            f"[TOOLSET_CREATE] Tool {idx}: type={type(item).__name__}, is_dict={isinstance(item, dict)}"
                        )
                        if isinstance(item, dict):
                            logger.info(f"[TOOLSET_CREATE] Tool {idx} keys: {list(item.keys())}")
                            has_handler = "handler" in item
                            has_callable_1 = 1 in item and callable(item.get(1))
                            logger.info(
                                f"[TOOLSET_CREATE] Tool {idx}: has_handler={has_handler}, has_callable_1={has_callable_1}"
                            )
                            if has_handler or has_callable_1:
                                has_inline_tools = True
                                break

                logger.info(f"[TOOLSET_CREATE] '{name}' has_inline_tools={has_inline_tools}")

                if has_inline_tools:
                    # Create toolset from inline Lua tools
                    logger.info(f"[TOOLSET_CREATE] Creating inline toolset for '{name}'")
                    try:
                        from tactus.adapters.lua_tools import LuaToolsAdapter

                        lua_adapter = LuaToolsAdapter(
                            tool_primitive=self.tool_primitive, mock_manager=self.mock_manager
                        )

                        # Create a toolset from inline tool definitions
                        toolset = lua_adapter.create_inline_toolset(name, tools_list)
                        logger.info(
                            f"[TOOLSET_CREATE] ✓ Created inline toolset '{name}': {toolset}"
                        )
                        return toolset
                    except Exception as e:
                        logger.error(
                            f"[TOOLSET_CREATE] ✗ Failed to create inline toolset '{name}': {e}",
                            exc_info=True,
                        )
                        return None
                else:
                    # Tools list contains tool names - create a combined toolset
                    from pydantic_ai.toolsets import CombinedToolset

                    resolved_tools = []
                    for tool_name in tools_list:
                        # Try to resolve each tool
                        tool = self.resolve_toolset(tool_name)
                        if tool:
                            resolved_tools.append(tool)
                        else:
                            logger.warning(f"Tool '{tool_name}' not found for toolset '{name}'")

                    if resolved_tools:
                        return CombinedToolset(resolved_tools)
                    else:
                        logger.error(f"No valid tools found for toolset '{name}'")
                        return None

            elif "use" in definition:
                # Import toolset from external source
                source = definition["use"]

                # Handle different source types
                if source.startswith("./") or source.endswith(".tac"):
                    # Import from local .tac file
                    from pathlib import Path

                    # Resolve path relative to the source file if available
                    if self.source_file_path and source.startswith("./"):
                        base_dir = Path(self.source_file_path).parent
                        file_path = base_dir / source[2:]  # Remove "./" prefix
                    else:
                        file_path = Path(source)

                    # Check if file exists
                    if not file_path.exists():
                        logger.error(f"Toolset source file not found: {file_path}")
                        return None

                    if not file_path.suffix == ".tac":
                        logger.error(f"Toolset source must be a .tac file: {file_path}")
                        return None

                    # For now, log a warning that this is partially implemented
                    # In a full implementation, we would:
                    # 1. Parse the .tac file
                    # 2. Extract all Tool and Toolset definitions
                    # 3. Create a combined toolset with all tools from the file
                    logger.warning(
                        f"Toolset import from .tac file '{file_path}' is partially implemented. "
                        "Currently returns empty toolset. Full implementation would extract all "
                        "tools and toolsets from the file."
                    )

                    # Return an empty toolset for now
                    from pydantic_ai.toolsets import FunctionToolset

                    return FunctionToolset(tools=[])

                elif source.startswith("mcp."):
                    # Reference MCP server
                    server_name = source[4:]  # Remove "mcp." prefix
                    return self.resolve_toolset(server_name)
                else:
                    logger.error(f"Unknown toolset source '{source}' for '{name}'")
                    return None

            else:
                logger.error(f"Toolset '{name}' has neither 'type', 'tools', nor 'use' field")
                return None

    def _parse_toolset_expressions(self, expressions: list) -> list:
        """
        Parse toolset expressions from agent config.

        Supports:
        - Simple string: "financial" -> entire toolset
        - Filter dict: {name = "plexus", include = ["score_info"]}
        - Exclude dict: {name = "web", exclude = ["admin"]}
        - Prefix dict: {name = "web", prefix = "search_"}
        - Rename dict: {name = "tools", rename = {old = "new"}}

        Args:
            expressions: List of toolset references or transformation dicts

        Returns:
            List of AbstractToolset instances
        """
        result = []

        for expr in expressions:
            if isinstance(expr, str):
                # Simple reference - resolve by name
                logger.debug(
                    f"Resolving toolset '{expr}' from registry with {len(self.toolset_registry)} entries"
                )
                toolset = self.resolve_toolset(expr)
                if toolset is None:
                    logger.error(f"Toolset '{expr}' not found in registry")
                    raise ValueError(f"Toolset '{expr}' not found")
                result.append(toolset)

            elif isinstance(expr, dict):
                # Transformation expression
                name = expr.get("name")
                if not name:
                    raise ValueError(f"Toolset expression missing 'name': {expr}")

                toolset = self.resolve_toolset(name)
                if toolset is None:
                    raise ValueError(f"Toolset '{name}' not found")

                # Apply transformations in order
                if "include" in expr:
                    # Filter to specific tools
                    tool_names = set(expr["include"])
                    toolset = toolset.filtered(
                        lambda execution_context, tool: tool.name in tool_names
                    )
                    logger.debug(f"Applied include filter to toolset '{name}': {tool_names}")

                if "exclude" in expr:
                    # Exclude specific tools
                    tool_names = set(expr["exclude"])
                    toolset = toolset.filtered(
                        lambda execution_context, tool: tool.name not in tool_names
                    )
                    logger.debug(f"Applied exclude filter to toolset '{name}': {tool_names}")

                if "prefix" in expr:
                    # Add prefix to tool names
                    prefix = expr["prefix"]
                    toolset = toolset.prefixed(prefix)
                    logger.debug(f"Applied prefix '{prefix}' to toolset '{name}'")

                if "rename" in expr:
                    # Rename tools
                    rename_map = expr["rename"]
                    toolset = toolset.renamed(rename_map)
                    logger.debug(f"Applied rename to toolset '{name}': {rename_map}")

                result.append(toolset)
            else:
                raise ValueError(f"Invalid toolset expression: {expr} (type: {type(expr)})")

        return result

    async def _initialize_dependencies(self):
        """Initialize user-declared dependencies from registry."""
        # Only initialize if registry exists and has dependencies
        if not self.registry or not self.registry.dependencies:
            logger.debug("No dependencies declared in procedure")
            return

        logger.info(f"Initializing {len(self.registry.dependencies)} dependencies")

        # Import dependency infrastructure
        from tactus.core.dependencies import ResourceFactory, ResourceManager

        # Create ResourceManager for lifecycle management
        self.dependency_manager = ResourceManager()

        # Build config dict for ResourceFactory
        dependencies_config = {}
        for dep_name, dep_decl in self.registry.dependencies.items():
            dependencies_config[dep_name] = dep_decl.config

        try:
            # Create all dependencies
            self.user_dependencies = await ResourceFactory.create_all(dependencies_config)

            # Register with manager for cleanup
            for dep_name, dep_instance in self.user_dependencies.items():
                await self.dependency_manager.add_resource(dep_name, dep_instance)

            logger.info(
                f"Successfully initialized dependencies: {list(self.user_dependencies.keys())}"
            )

        except Exception as e:
            logger.error(f"Failed to initialize dependencies: {e}")
            raise RuntimeError(f"Dependency initialization failed: {e}")

    async def _setup_agents(self, context: dict[str, Any]):
        """
        Setup agent primitives with LLMs and tools using Pydantic AI.

        Args:
            context: Procedure context with pre-loaded data
        """
        import sys  # For debug output

        logger.info(
            f"_setup_agents called. Toolset registry has {len(self.toolset_registry)} toolsets: {list(self.toolset_registry.keys())}"
        )

        # Initialize user dependencies first (needed by agents)
        await self._initialize_dependencies()

        # Get agent configurations from registry (Lua-parsed) if available, otherwise from YAML config
        if hasattr(self, "registry") and self.registry and hasattr(self.registry, "agents"):
            agents_config = self.registry.agents
            logger.info(
                f"Using {len(agents_config)} agent(s) from registry: {list(agents_config.keys())}"
            )
        else:
            agents_config = self.config.get("agents", {})
            logger.info(f"Using {len(agents_config)} agent(s) from YAML config")

        if not agents_config:
            logger.info("No agents defined in configuration - skipping agent setup")
            return

        # Import DSPy agent primitive (required)
        from tactus.dspy.agent import create_dspy_agent

        logger.info("Using DSPy-based Agent implementation")

        # Get default toolsets from config (for agents that don't specify toolsets)
        default_toolset_names = self.config.get("default_toolsets", [])
        if default_toolset_names:
            logger.info(f"Default toolsets configured: {default_toolset_names}")

        # Setup each agent
        for agent_name, agent_config_raw in agents_config.items():
            # Convert AgentDeclaration to dict if needed
            if hasattr(agent_config_raw, "model_dump"):
                # Pydantic v2
                agent_config = agent_config_raw.model_dump()
            elif hasattr(agent_config_raw, "dict"):
                # Pydantic v1
                agent_config = agent_config_raw.dict()
            else:
                # Already a dict
                agent_config = agent_config_raw

            # Skip if agent was already created during immediate initialization
            if agent_name in self.agents:
                logger.debug(
                    f"Agent '{agent_name}' already created during parsing - skipping setup"
                )
                continue

            logger.info(f"Setting up agent: {agent_name}")

            # Get agent prompts (initial_message needs template processing, system_prompt is dynamic)
            system_prompt_template = agent_config[
                "system_prompt"
            ]  # Keep as template for dynamic rendering

            # initial_message is optional - if not provided, will default to empty string or manual injection
            initial_message_raw = agent_config.get("initial_message", "")
            initial_message = (
                self._process_template(initial_message_raw, context) if initial_message_raw else ""
            )

            # Provider is required - no defaults
            provider_name = agent_config.get("provider") or self.config.get("default_provider")
            if not provider_name:
                raise ValueError(
                    f"Agent '{agent_name}' must specify a 'provider' (either on the agent or as 'default_provider' in the procedure)"
                )

            # Handle model - can be string or dict with settings
            model_config = agent_config.get("model") or self.config.get("default_model") or "gpt-4o"
            model_settings = None

            if isinstance(model_config, dict):
                # Model is a dict with name and settings
                model_id = model_config.get("name")
                # Extract settings (everything except 'name')
                model_settings = {k: v for k, v in model_config.items() if k != "name"}
                if model_settings:
                    logger.info(f"Agent '{agent_name}' using model settings: {model_settings}")
            else:
                # Model is a simple string
                model_id = model_config

            # If model_id has a provider prefix AND no explicit provider was set, extract it
            if (
                ":" in model_id
                and not agent_config.get("provider")
                and not self.config.get("default_provider")
            ):
                prefix, model_id = model_id.split(":", 1)
                provider_name = prefix

            # Construct the full model string for pydantic-ai
            model_name = f"{provider_name}:{model_id}"

            logger.info(
                f"Agent '{agent_name}' using provider '{provider_name}' with model '{model_id}'"
            )

            # Handle inline Lua function tools (agent.inline_tools)
            inline_tools_toolset = None
            if "inline_tools" in agent_config and agent_config["inline_tools"]:
                tools_spec = agent_config["inline_tools"]
                # These are inline tool definitions (dicts with 'handler' key)
                if isinstance(tools_spec, list):
                    inline_tool_specs = [
                        t
                        for t in tools_spec
                        if isinstance(t, dict)
                        and ("handler" in t or (1 in t and callable(t.get(1))))
                    ]
                    if inline_tool_specs:
                        # These are inline Lua function tools
                        try:
                            from tactus.adapters.lua_tools import LuaToolsAdapter

                            lua_adapter = LuaToolsAdapter(
                                tool_primitive=self.tool_primitive, mock_manager=self.mock_manager
                            )
                            inline_tools_toolset = lua_adapter.create_inline_tools_toolset(
                                agent_name, inline_tool_specs
                            )
                            logger.info(
                                f"Agent '{agent_name}' has {len(inline_tool_specs)} inline Lua tools"
                            )
                        except ImportError as e:
                            logger.error(
                                f"Could not import LuaToolsAdapter for agent '{agent_name}': {e}"
                            )

            # Get tools (tool/toolset references) for this agent
            # Use a sentinel value to distinguish "not present" from "present but None/empty"
            _MISSING = object()
            agent_tools_config = agent_config.get("tools", _MISSING)

            # Debug log
            logger.debug(
                f"Agent '{agent_name}' raw tools config: {agent_tools_config}, type: {type(agent_tools_config)}"
            )

            # Convert Lua table to Python list if needed
            if (
                agent_tools_config is not _MISSING
                and agent_tools_config is not None
                and hasattr(agent_tools_config, "__len__")
            ):
                try:
                    # Try to convert Lua table to list
                    agent_tools_config = (
                        list(agent_tools_config.values())
                        if hasattr(agent_tools_config, "values")
                        else list(agent_tools_config)
                    )
                    logger.debug(f"Agent '{agent_name}' converted tools to: {agent_tools_config}")
                except (TypeError, AttributeError):
                    # If conversion fails, leave as-is
                    pass

            if agent_tools_config is _MISSING:
                # No tools key present - use default toolsets if configured, otherwise all
                if default_toolset_names:
                    filtered_toolsets = self._parse_toolset_expressions(default_toolset_names)
                    logger.info(
                        f"Agent '{agent_name}' using default toolsets: {default_toolset_names}"
                    )
                else:
                    # No defaults configured - use all available toolsets from registry
                    filtered_toolsets = list(self.toolset_registry.values())
                    logger.info(
                        f"Agent '{agent_name}' using all available toolsets (no defaults configured)"
                    )
            elif isinstance(agent_tools_config, list) and len(agent_tools_config) == 0:
                # Explicitly empty list - no tools
                # Use None instead of [] to completely disable tool calling for Bedrock models
                filtered_toolsets = None
                logger.info(f"Agent '{agent_name}' has NO tools (explicitly empty - passing None)")
            else:
                # Parse toolset expressions
                sys.stderr.write(
                    f"\n[AGENT_SETUP] Agent '{agent_name}' raw tools config: {agent_tools_config}\n"
                )
                sys.stderr.write(
                    f"[AGENT_SETUP] toolset_registry has: {list(self.toolset_registry.keys())}\n"
                )
                sys.stderr.flush()
                logger.info(f"Agent '{agent_name}' raw tools config: {agent_tools_config}")
                filtered_toolsets = self._parse_toolset_expressions(agent_tools_config)
                sys.stderr.write(
                    f"[AGENT_SETUP] Agent '{agent_name}' parsed toolsets: {filtered_toolsets}\n"
                )
                sys.stderr.flush()
                logger.info(f"Agent '{agent_name}' parsed toolsets: {filtered_toolsets}")

            # Append inline tools toolset if present
            if inline_tools_toolset:
                if filtered_toolsets is None:
                    # Agent had no toolsets, create list with just inline tools
                    filtered_toolsets = [inline_tools_toolset]
                else:
                    # Append to existing toolsets
                    filtered_toolsets.append(inline_tools_toolset)
                logger.debug(f"Added inline tools toolset to agent '{agent_name}'")

            # Legacy: Keep empty tools list for AgentPrimitive constructor
            filtered_tools = []

            # Handle structured output if specified
            output_schema = None  # Initialize for DSPy agent

            # Prefer output (aligned with pydantic-ai)
            if agent_config.get("output"):
                try:
                    self._create_pydantic_model_from_output(
                        agent_config["output"], f"{agent_name}Output"
                    )
                    logger.info(f"Using agent output schema for '{agent_name}'")
                    # Also set output_schema for DSPy compatibility
                    output_schema = agent_config["output"]
                except Exception as e:
                    logger.warning(f"Failed to create output model from output: {e}")
            elif agent_config.get("output_schema"):
                # Fallback to output_schema for backward compatibility
                output_schema = agent_config["output_schema"]
                try:
                    self._create_output_model_from_schema(output_schema, f"{agent_name}Output")
                    logger.info(f"Created structured output model for agent '{agent_name}'")
                except Exception as e:
                    logger.warning(f"Failed to create output model for agent '{agent_name}': {e}")
            elif self.config.get("output"):
                # Procedure-level output schemas apply to procedures, not agents.
                # Only use them as a fallback for agent structured output when they are
                # object-shaped (i.e., a dict of fields). Scalar procedure outputs
                # (e.g., `output = field.string{...}`) are not agent output schemas.
                procedure_output_schema = self.config["output"]
                if (
                    isinstance(procedure_output_schema, dict)
                    and "type" not in procedure_output_schema
                ):
                    output_schema = procedure_output_schema
                    try:
                        self._create_output_model_from_schema(output_schema, f"{agent_name}Output")
                        logger.info(f"Using procedure-level output schema for agent '{agent_name}'")
                    except Exception as e:
                        logger.warning(f"Failed to create output model from procedure schema: {e}")

            # Extract message history filter if configured
            message_history_filter = None
            if agent_config.get("message_history"):
                message_history_config = agent_config["message_history"]
                if isinstance(message_history_config, dict) and "filter" in message_history_config:
                    message_history_filter = message_history_config["filter"]
                    logger.info(
                        f"Agent '{agent_name}' has message history filter: {message_history_filter}"
                    )

            # Create DSPy-based agent
            tool_choice = agent_config.get("tool_choice")
            logger.info(f"Agent '{agent_name}' config has tool_choice={tool_choice}")

            dspy_config = {
                "system_prompt": system_prompt_template,
                "model": model_name,
                "provider": agent_config.get("provider"),
                "tools": filtered_tools,
                "toolsets": filtered_toolsets,
                "output_schema": output_schema,
                "temperature": (
                    model_settings.get("temperature", 0.7)
                    if model_settings
                    else agent_config.get("temperature", 0.7)
                ),
                "max_tokens": (
                    model_settings.get("max_tokens")
                    if model_settings
                    else agent_config.get("max_tokens")
                ),
                "model_type": (
                    model_settings.get("model_type")
                    if model_settings
                    else agent_config.get("model_type")
                ),
                "disable_streaming": agent_config.get("disable_streaming", False),
                "initial_message": initial_message,
                "log_handler": self.log_handler,
                "tool_choice": tool_choice,  # Pass through tool_choice
            }
            logger.info(
                f"Agent '{agent_name}' dspy_config has tool_choice={dspy_config.get('tool_choice')}"
            )

            # Create DSPy agent with registry, mock_manager, and execution_context
            agent_primitive = create_dspy_agent(
                agent_name,
                dspy_config,
                registry=self.registry,
                mock_manager=self.mock_manager,
                execution_context=self.execution_context,
            )

            # Store additional context for compatibility
            agent_primitive._tool_primitive = self.tool_primitive
            agent_primitive._state_primitive = self.state_primitive
            agent_primitive._context = context

            self.agents[agent_name] = agent_primitive

            # CRITICAL FIX: Update the Lua global to point to the new agent with toolsets
            # The agent was created during parsing WITHOUT toolsets, now we update it
            # to the new agent that HAS toolsets
            self.lua_sandbox.lua.globals()[agent_name] = agent_primitive
            sys.stderr.write(
                f"[AGENT_FIX] Updated Lua global '{agent_name}' to new agent with toolsets\n"
            )
            sys.stderr.flush()

            logger.info(f"Agent '{agent_name}' configured successfully with model '{model_name}'")

    async def _setup_models(self):
        """
        Setup model primitives for ML inference.

        Creates ModelPrimitive instances for each model declaration
        and stores them in self.models dict.
        """
        # Get model configurations from registry
        if not self.registry or not self.registry.models:
            logger.debug("No models defined in configuration - skipping model setup")
            return

        from tactus.primitives.model import ModelPrimitive

        # Setup each model
        for model_name, model_config in self.registry.models.items():
            logger.info(f"Setting up model: {model_name}")

            try:
                model_primitive = ModelPrimitive(
                    model_name=model_name,
                    config=model_config,
                    context=self.execution_context,
                    mock_manager=self.mock_manager,
                )

                self.models[model_name] = model_primitive
                logger.info(f"Model '{model_name}' configured successfully")

            except Exception as e:
                logger.error(f"Failed to setup model '{model_name}': {e}")
                raise

    def _create_pydantic_model_from_output(self, output_schema: Any, model_name: str) -> type:
        """
        Convert output schema to Pydantic model.

        Aligned with pydantic-ai's output parameter.

        Args:
            output_schema: AgentOutputSchema or dict with field definitions
            model_name: Name for the generated Pydantic model

        Returns:
            Dynamically created Pydantic model class
        """
        from pydantic import create_model

        fields = {}

        # Handle AgentOutputSchema object
        if hasattr(output_schema, "fields"):
            schema_fields = output_schema.fields
        else:
            # Assume it's a dict
            schema_fields = output_schema

        for field_name, field_def in schema_fields.items():
            # Extract field properties
            if hasattr(field_def, "type"):
                field_type_str = field_def.type
                is_required = getattr(field_def, "required", True)
            else:
                # Fields from registry are plain dicts (FieldDefinition type is lost)
                # Trust that they were created with field builders
                field_type_str = field_def.get("type", "string")
                is_required = field_def.get("required", True)

            # Map type string to Python type
            field_type = self._map_type_string(field_type_str)

            # Create field tuple (type, default_or_required)
            if is_required:
                fields[field_name] = (field_type, ...)  # Required field
            else:
                fields[field_name] = (field_type | None, None)  # Optional field

        return create_model(model_name, **fields)

    def _map_type_string(self, type_str: str) -> type:
        """Map type string to Python type."""
        type_map = {
            "string": str,
            "str": str,
            "number": float,
            "float": float,
            "integer": int,
            "int": int,
            "boolean": bool,
            "bool": bool,
            "object": dict,
            "dict": dict,
            "array": list,
            "list": list,
        }
        return type_map.get(type_str.lower(), str)

    def _create_output_model_from_schema(
        self, output_schema: dict[str, Any], model_name: str = "OutputModel"
    ) -> type:
        """
        Create a Pydantic model from output schema definition.

        Args:
            output_schema: Dictionary mapping field names to field definitions
            model_name: Name for the generated model

        Returns:
            Pydantic model class
        """
        from pydantic import create_model, Field  # noqa: F401

        fields = {}
        for field_name, field_def in output_schema.items():
            # Fields from registry are plain dicts (FieldDefinition type is lost)
            # Trust that they were created with field builders
            field_type_str = field_def.get("type", "string")
            is_required = field_def.get("required", False)

            # Map type strings to Python types
            type_mapping = {
                "string": str,
                "integer": int,
                "number": float,
                "boolean": bool,
                "array": list,
                "object": dict,
            }
            python_type = type_mapping.get(field_type_str, str)

            # Create Field with description if available
            description = field_def.get("description", "")
            if is_required:
                field = (
                    Field(..., description=description) if description else Field(...)  # noqa: F821
                )
            else:
                default = field_def.get("default", None)
                field = (
                    Field(default=default, description=description)  # noqa: F821
                    if description
                    else Field(default=default)  # noqa: F821
                )

            fields[field_name] = (python_type, field)

        return create_model(model_name, **fields)  # noqa: F821

    def _enhance_handles(self):
        """
        Connect DSL handles to their actual primitives (fallback for handles not already connected).

        With immediate agent creation, most handles are already connected during parsing.
        This method now serves as a fallback for:
        - Handles created before runtime context was available
        - Model handles (which may still use two-phase initialization)
        - Cases where immediate creation failed

        This is called from _inject_primitives() after all primitives are ready.
        """
        from tactus.primitives.handles import AgentHandle, ModelHandle

        # Get registries (stored during _parse_dsl_source)
        if not hasattr(self, "_dsl_registries"):
            logger.debug("No DSL registries found - skipping handle enhancement")
            return

        agent_registry = self._dsl_registries.get("agent", {})
        model_registry = self._dsl_registries.get("model", {})

        # Enhance agent handles (only if not already connected)
        enhanced_count = 0
        execution_context_updated_count = 0
        for agent_name, primitive in self.agents.items():
            if agent_name in agent_registry:
                handle = agent_registry[agent_name]
                if isinstance(handle, AgentHandle):
                    # Only enhance if not already connected
                    if handle._primitive is None:
                        handle._set_primitive(primitive, self.execution_context)
                        logger.info(f"Enhanced AgentHandle '{agent_name}' (fallback)")
                        enhanced_count += 1
                    else:
                        # For immediate agents: primitive is already connected but execution_context might be None
                        # Update execution_context if needed (it wasn't available during parsing)
                        if handle._execution_context is None and self.execution_context is not None:
                            handle._execution_context = self.execution_context
                            logger.info(
                                f"[CHECKPOINT] Updated execution_context for immediately-created agent '{agent_name}', handle id={id(handle)}, handle in Lua globals={agent_name in self.lua_sandbox.lua.globals()}"
                            )
                            execution_context_updated_count += 1
                        else:
                            logger.debug(f"AgentHandle '{agent_name}' already connected - skipping")
                else:
                    logger.warning(
                        f"Agent registry entry '{agent_name}' is not an AgentHandle: {type(handle)}"
                    )

        # Enhance model handles (only if not already connected)
        for model_name, primitive in self.models.items():
            if model_name in model_registry:
                handle = model_registry[model_name]
                if isinstance(handle, ModelHandle):
                    if handle._primitive is None:
                        handle._set_primitive(primitive)
                        logger.info(f"Enhanced ModelHandle '{model_name}' (fallback)")
                        enhanced_count += 1
                    else:
                        logger.debug(f"ModelHandle '{model_name}' already connected - skipping")
                else:
                    logger.warning(
                        f"Model registry entry '{model_name}' is not a ModelHandle: {type(handle)}"
                    )

        if enhanced_count > 0:
            logger.debug(f"Handle enhancement (fallback) connected {enhanced_count} handles")
        elif execution_context_updated_count > 0:
            logger.info(
                f"[CHECKPOINT] Updated execution_context for {execution_context_updated_count} immediately-created agents"
            )
        else:
            logger.debug("All handles already connected during parsing")

    def _inject_primitives(self):
        """Inject all primitives into Lua global scope."""
        # Inject input with default values, then override with context values
        if "input" in self.config:
            input_config = self.config["input"]
            input_values = {}
            # Start with defaults
            for input_name, input_def in input_config.items():
                if isinstance(input_def, dict) and "default" in input_def:
                    input_values[input_name] = input_def["default"]
            # Override with context values
            for input_name in input_config.keys():
                if input_name in self.context:
                    input_values[input_name] = self.context[input_name]

            # Validate enum constraints
            for input_name, input_value in input_values.items():
                if input_name in input_config:
                    input_def = input_config[input_name]
                    if isinstance(input_def, dict) and "enum" in input_def and input_def["enum"]:
                        allowed_values = input_def["enum"]
                        if input_value not in allowed_values:
                            raise ValueError(
                                f"Input '{input_name}' has invalid value '{input_value}'. "
                                f"Allowed values: {allowed_values}"
                            )

            # Convert Python lists/dicts to Lua tables for proper array/object handling
            def convert_to_lua(value):
                """Recursively convert Python lists and dicts to Lua tables."""
                if isinstance(value, list):
                    # Convert Python list to Lua table (1-indexed)
                    lua_table = self.lua_sandbox.lua.table()
                    for index, item in enumerate(value, 1):
                        lua_table[index] = convert_to_lua(item)
                    return lua_table
                elif isinstance(value, dict):
                    # Convert Python dict to Lua table
                    lua_table = self.lua_sandbox.lua.table()
                    for key, item in value.items():
                        lua_table[key] = convert_to_lua(item)
                    return lua_table
                else:
                    return value

            # Convert all inputs, creating a new Lua table for the input object
            lua_input = self.lua_sandbox.lua.table()
            for key, value in input_values.items():
                lua_input[key] = convert_to_lua(value)

            self.lua_sandbox.set_global("input", lua_input)
            logger.info(f"Injected input into Lua sandbox: {input_values}")

        # Re-inject state primitive (may have been updated with schema)
        if self.state_primitive:
            # Replace the placeholder _state_primitive with the real one
            # (The metatable was already set up during parsing, so it will use this new primitive)
            self.lua_sandbox.inject_primitive("_state_primitive", self.state_primitive)
            logger.debug(
                "State primitive re-injected (metatable already configured during parsing)"
            )
        if self.iterations_primitive:
            self.lua_sandbox.inject_primitive("Iterations", self.iterations_primitive)
        if self.stop_primitive:
            self.lua_sandbox.inject_primitive("Stop", self.stop_primitive)
        if self.tool_primitive:
            self.lua_sandbox.inject_primitive("Tool", self.tool_primitive)
        if self.toolset_primitive:
            self.lua_sandbox.inject_primitive("Toolset", self.toolset_primitive)
            logger.info(f"Injecting Toolset primitive: {self.toolset_primitive}")

        # Inject checkpoint primitives
        if self.step_primitive:
            self.lua_sandbox.inject_primitive("Step", self.step_primitive)

            # Inject checkpoint as _python_checkpoint, then wrap it with Lua code
            # that captures source location using debug.getinfo
            self.lua_sandbox.inject_primitive("_python_checkpoint", self.step_primitive.checkpoint)

            # Create Lua wrapper that captures source location before calling Python
            self.lua_sandbox.lua.execute(
                """
                function checkpoint(fn)
                    -- Capture caller's source location (2 levels up: this wrapper -> caller)
                    local info = debug.getinfo(2, 'Sl')
                    if info then
                        local source_info = {
                            file = info.source,
                            line = info.currentline or 0
                        }
                        -- Call Python checkpoint with source location
                        return _python_checkpoint(fn, source_info)
                    else
                        -- Fallback if debug info not available
                        return _python_checkpoint(fn, nil)
                    end
                end
            """
            )
            logger.debug("Checkpoint wrapper injected with Lua source location tracking")

        if self.checkpoint_primitive:
            self.lua_sandbox.inject_primitive("Checkpoint", self.checkpoint_primitive)
            logger.debug("Step and Checkpoint primitives injected")

        # Inject HITL primitives
        if self.human_primitive:
            logger.info(f"Injecting Human primitive: {self.human_primitive}")
            self.lua_sandbox.inject_primitive("Human", self.human_primitive)

        if self.log_primitive:
            logger.info(f"Injecting Log primitive: {self.log_primitive}")
            self.lua_sandbox.inject_primitive("Log", self.log_primitive)

        if self.message_history_primitive:
            logger.info(f"Injecting MessageHistory primitive: {self.message_history_primitive}")
            self.lua_sandbox.inject_primitive("MessageHistory", self.message_history_primitive)

        if self.json_primitive:
            logger.info(f"Injecting Json primitive: {self.json_primitive}")
            self.lua_sandbox.inject_primitive("Json", self.json_primitive)

        if self.retry_primitive:
            logger.info(f"Injecting Retry primitive: {self.retry_primitive}")
            self.lua_sandbox.inject_primitive("Retry", self.retry_primitive)

        if self.file_primitive:
            logger.info(f"Injecting File primitive: {self.file_primitive}")
            self.lua_sandbox.inject_primitive("File", self.file_primitive)

        if self.procedure_primitive:
            logger.info(f"Injecting Procedure primitive: {self.procedure_primitive}")
            self.lua_sandbox.inject_primitive("Procedure", self.procedure_primitive)

        if self.system_primitive:
            logger.info(f"Injecting System primitive: {self.system_primitive}")
            self.lua_sandbox.inject_primitive("System", self.system_primitive)

        if self.host_primitive:
            logger.info(f"Injecting Host primitive: {self.host_primitive}")
            self.lua_sandbox.inject_primitive("Host", self.host_primitive)

        # Inject Sleep function
        def sleep_wrapper(seconds):
            """Sleep for specified number of seconds."""
            logger.info(f"Sleep({seconds}) - pausing execution")
            time.sleep(seconds)
            logger.info(f"Sleep({seconds}) - resuming execution")

        self.lua_sandbox.set_global("Sleep", sleep_wrapper)
        logger.info("Injected Sleep function")

        # NOTE: Agent and model primitives are NO LONGER auto-injected with capitalized names.
        # Instead, use the new syntax:
        #   agent "greeter" { config }     -- define
        #   Agent("greeter")()             -- lookup and call
        # Or assign during definition:
        #   Greeter = agent "greeter" { config }
        #   Greeter()                      -- callable syntax

        # Enhance DSL handles to connect them to actual primitives
        self._enhance_handles()

        logger.debug("All primitives injected into Lua sandbox")

    def _execute_workflow(self) -> Any:
        """
        Execute the Lua procedure code.

        Looks for named 'main' procedure first, falls back to anonymous procedure.

        Returns:
            Result from Lua procedure execution
        """
        if self.registry:
            # Check for named 'main' procedure first
            if "main" in self.registry.named_procedures:
                logger.info("Executing named 'main' procedure")
                try:
                    main_proc = self.registry.named_procedures["main"]

                    logger.debug(
                        f"Executing main: function={main_proc['function']}, "
                        f"type={type(main_proc['function'])}"
                    )

                    # Create callable wrapper for main
                    from tactus.primitives.procedure_callable import ProcedureCallable

                    main_callable = ProcedureCallable(
                        name="main",
                        procedure_function=main_proc["function"],
                        input_schema=main_proc["input_schema"],
                        output_schema=main_proc["output_schema"],
                        state_schema=main_proc["state_schema"],
                        execution_context=self.execution_context,
                        lua_sandbox=self.lua_sandbox,
                        is_main=True,  # Main procedure is not checkpointed
                    )

                    # Gather input parameters from context, applying defaults
                    input_params = {}
                    for key, field_def in main_proc["input_schema"].items():
                        # Check context first
                        if hasattr(self, "context") and self.context and key in self.context:
                            input_params[key] = self.context[key]
                        # Apply default if available and not required
                        elif isinstance(field_def, dict) and "default" in field_def:
                            # Fields created by field builders will have proper structure
                            # We can't check FieldDefinition type here as it's lost during storage
                            input_params[key] = field_def["default"]
                        # If required and not in context, it will fail validation in ProcedureCallable
                    logger.debug(f"Calling main with input_params: {input_params}")

                    # Set procedure metadata for HITL context display
                    if hasattr(self, "execution_context") and self.execution_context:
                        self.execution_context.set_procedure_metadata(
                            procedure_name=main_proc.get("name", "main"), input_data=input_params
                        )

                    # Execute main procedure
                    result = main_callable(input_params)

                    # Convert Lua table result to Python dict if needed
                    # Check for lupa table (not Python dict/list)
                    if (
                        result is not None
                        and hasattr(result, "items")
                        and not isinstance(result, (dict, list))
                    ):
                        result = lua_table_to_dict(result)

                    logger.info("Named 'main' procedure execution completed successfully")
                    return result
                except ProcedureWaitingForHuman:
                    # Re-raise without wrapping - this is expected behavior
                    raise
                except Exception as e:
                    logger.error(f"Named 'main' procedure execution failed: {e}")
                    raise LuaSandboxError(f"Named 'main' procedure execution failed: {e}")

            else:
                # No main procedure found - check if we have top-level execution result
                if hasattr(self, "_top_level_result") and self._top_level_result is not None:
                    logger.info("No main Procedure found - using top-level execution result")
                    return self._top_level_result
                else:
                    raise RuntimeError("Named 'main' procedure not found in registry")

        # Legacy YAML: execute procedure code string
        procedure_code = self.config["procedure"]
        logger.debug(f"Executing legacy procedure code ({len(procedure_code)} bytes)")

        try:
            result = self.lua_sandbox.execute(procedure_code)
            logger.info("Legacy procedure execution completed successfully")
            return result

        except LuaSandboxError as e:
            logger.error(f"Legacy procedure execution failed: {e}")
            raise

    def _maybe_transform_script_mode_source(self, source: str) -> str:
        """
        Transform "script mode" source into an implicit Procedure wrapper.

        Script mode allows:
          input { ... }
          output { ... }
          -- declarations (Agent/Tool/Mocks/etc.)
          -- executable code
          return {...}

        During parsing, the Lua chunk is executed to collect declarations, but agents
        are not yet wired to toolsets/LLMs. Without transformation, top-level code
        would execute too early. We split declaration blocks from executable code and
        wrap the executable portion into an implicit `Procedure { function(input) ... end }`.
        """
        import re

        # If an explicit Procedure exists (any syntax), do not transform.
        # Examples:
        #   Procedure { ... }
        #   main = Procedure { ... }
        #   Procedure "main" { ... }
        #   main = Procedure "main" { ... }
        if re.search(r"(?m)^\s*(?:[A-Za-z_][A-Za-z0-9_]*\s*=\s*)?Procedure\b", source):
            return source

        # If there are named function definitions (function name()), don't transform.
        # These are procedure definitions that will be explicitly called.
        if re.search(r"(?m)^\s*(?:local\s+)?function\s+[A-Za-z_][A-Za-z0-9_]*\s*\(", source):
            return source

        # Detect script mode by top-level input/output declarations OR a top-level `return`.
        # We intentionally treat simple "hello world" scripts as script-mode so agent/tool
        # calls don't execute during the parse/declaration phase.
        if not re.search(r"(?m)^\s*(input|output)\s*\{", source) and not re.search(
            r"(?m)^\s*return\b", source
        ):
            return source

        # Split into declaration prefix vs executable body.
        decl_lines: list[str] = []
        body_lines: list[str] = []

        # Once we enter executable code, everything stays in the body.
        in_body = False
        brace_depth = 0
        function_depth = 0  # Track function...end blocks
        long_string_eq: str | None = None

        decl_start = re.compile(
            r"^\s*(?:"
            r"input|output|Mocks|Agent|Toolset|Tool|Model|Module|Signature|LM|Dependency|Prompt|"
            r"Specifications|Evaluation|Evaluations|"
            r"default_provider|default_model|return_prompt|error_prompt|status_prompt|async|"
            r"max_depth|max_turns"
            r")\b"
        )
        require_stmt = re.compile(r"^\s*(?:local\s+)?[A-Za-z_][A-Za-z0-9_]*\s*=\s*require\(")
        assignment_decl = re.compile(
            r"^\s*[A-Za-z_][A-Za-z0-9_]*\s*=\s*(?:"
            r"Agent|Toolset|Tool|Model|Module|Signature|LM|Dependency|Prompt"
            r")\b"
        )
        # Match function definitions: function name() or local function name()
        function_def = re.compile(r"^\s*(?:local\s+)?function\s+[A-Za-z_][A-Za-z0-9_]*\s*\(")

        long_string_open = re.compile(r"\[(=*)\[")

        for line in source.splitlines():
            if in_body:
                body_lines.append(line)
                continue

            stripped = line.strip()

            # If we're inside a Lua long-bracket string (e.g., Specification([[ ... ]]) / Specifications([[ ... ]]))
            # keep consuming lines as declarations until we see the closing delimiter.
            if long_string_eq is not None:
                decl_lines.append(line)
                if f"]{long_string_eq}]" in line:
                    long_string_eq = None
                continue

            # If we're inside a declaration block, keep consuming until braces/functions balance.
            added_to_decl = False
            if brace_depth > 0 or function_depth > 0:
                decl_lines.append(line)
                added_to_decl = True
            elif stripped == "" or stripped.startswith("--"):
                decl_lines.append(line)
                added_to_decl = True
            elif (
                decl_start.match(line)
                or assignment_decl.match(line)
                or require_stmt.match(line)
                or function_def.match(line)
            ):
                decl_lines.append(line)
                added_to_decl = True
            else:
                in_body = True
                body_lines.append(line)

            # Track Lua long-bracket strings opened in the declaration prefix (e.g. Specification([[...]])).
            # We only need a lightweight heuristic here; spec/eval blocks should be simple and well-formed.
            if added_to_decl:
                m = long_string_open.search(line)
                if m:
                    eq = m.group(1)
                    # If the opening and closing are on the same line, don't enter long-string mode.
                    if f"]{eq}]" not in line[m.end() :]:
                        long_string_eq = eq

            # Update brace depth based on a lightweight heuristic (sufficient for DSL blocks).
            # This intentionally ignores Lua string/comment edge cases; declarations should be simple.
            brace_depth += line.count("{") - line.count("}")
            if brace_depth < 0:
                brace_depth = 0

            # Track function...end blocks for named function definitions
            # Count 'function' keywords (both named and anonymous)
            # Note: This is a simple heuristic that counts keywords in comments/strings too,
            # but that's acceptable for well-formed DSL code
            import re as re_module

            function_count = len(re_module.findall(r"\bfunction\b", line))
            end_count = len(re_module.findall(r"\bend\b", line))
            function_depth += function_count - end_count
            if function_depth < 0:
                function_depth = 0

        # If there is no executable code, nothing to wrap.
        if not any(line.strip() for line in body_lines):
            return source

        # Indent executable code inside the implicit procedure function.
        indented_body = "\n".join(("    " + line) if line != "" else "" for line in body_lines)

        transformed = "\n".join(
            [
                *decl_lines,
                "",
                "Procedure {",
                "    function(input)",
                indented_body,
                "    end",
                "}",
                "",
            ]
        )

        return transformed

    def _process_template(self, template: str, context: dict[str, Any]) -> str:
        """
        Process a template string with variable substitution.

        Args:
            template: Template string with {variable} placeholders
            context: Context dict with variable values

        Returns:
            Processed string with variables substituted
        """
        try:
            # Build template variables from context (supports dot notation)
            from string import Formatter

            class DotFormatter(Formatter):
                def get_field(self, field_name, args, kwargs):
                    # Support dot notation like {params.topic}
                    path_parts = field_name.split(".")
                    current_value = kwargs
                    for part in path_parts:
                        if isinstance(current_value, dict):
                            current_value = current_value.get(part, "")
                        else:
                            current_value = getattr(current_value, part, "")
                    return current_value, field_name

            template_vars = {}

            # Add context variables
            if context:
                template_vars.update(context)

            # Add input from config with default values
            if "input" in self.config:
                input_config = self.config["input"]
                input_values = {}
                for input_name, input_def in input_config.items():
                    if isinstance(input_def, dict) and "default" in input_def:
                        input_values[input_name] = input_def["default"]
                template_vars["input"] = input_values

            # Add state (for dynamic templates)
            if self.state_primitive:
                template_vars["state"] = self.state_primitive.all()

            # Use dot-notation formatter
            formatter = DotFormatter()
            resolved_template = formatter.format(template, **template_vars)
            return resolved_template

        except KeyError as exception:
            logger.warning(f"Template variable {exception} not found, using template as-is")
            return template

        except Exception as exception:
            logger.error(f"Error processing template: {exception}")
            return template

    def _format_output_schema_for_prompt(self) -> str:
        """
        Format the output schema as guidance for LLM prompts.

        Returns:
            Formatted string describing expected outputs
        """
        outputs = self.config.get("output", {})
        if not outputs:
            return ""

        lines = ["## Expected Output Format", ""]
        lines.append("This workflow must return a structured result with the following fields:")
        lines.append("")

        # Format each output field
        for field_name, field_def in outputs.items():
            # Fields from registry are plain dicts (FieldDefinition type is lost)
            # Trust that they were created with field builders
            field_type = field_def.get("type", "any")
            is_required = field_def.get("required", False)
            description = field_def.get("description", "")

            req_marker = "**REQUIRED**" if is_required else "*optional*"
            lines.append(f"- **{field_name}** ({field_type}) - {req_marker}")
            if description:
                lines.append(f"  {description}")
            lines.append("")

        lines.append(
            "Note: The workflow orchestration code will extract and format these values from your tool calls and actions."
        )

        return "\n".join(lines)

    def get_state(self) -> dict[str, Any]:
        """Get current procedure state."""
        if self.state_primitive:
            return self.state_primitive.all()
        return {}

    def get_iteration_count(self) -> int:
        """Get current iteration count."""
        if self.iterations_primitive:
            return self.iterations_primitive.current()
        return 0

    def is_stopped(self) -> bool:
        """Check if procedure was stopped."""
        if self.stop_primitive:
            return self.stop_primitive.requested()
        return False

    def _parse_declarations(
        self, source: str, tool_primitive: ToolPrimitive | None = None
    ) -> ProcedureRegistry:
        """
        Execute .tac to collect declarations.

        Args:
            source: Lua DSL source code
            tool_primitive: Optional ToolPrimitive for creating callable ToolHandles

        Returns:
            ProcedureRegistry with all declarations

        Raises:
            TactusRuntimeError: If validation fails
        """
        builder = RegistryBuilder()

        # Use the existing sandbox so procedure functions have access to primitives
        sandbox = self.lua_sandbox

        # Build runtime context for immediate agent creation
        runtime_context = {
            "tool_primitive": tool_primitive,
            "registry": builder.registry,
            "mock_manager": self.mock_manager,
            "execution_context": self.execution_context,
            "log_handler": self.log_handler,
            "_created_agents": {},  # Will be populated during parsing
        }

        # Inject DSL stubs (pass tool_primitive, mock_manager, and runtime_context)
        stubs = create_dsl_stubs(
            builder, tool_primitive, mock_manager=self.mock_manager, runtime_context=runtime_context
        )

        # Register any agents that were created immediately during parsing
        created_agents = runtime_context.get("_created_agents", {})
        logger.info(
            f"[AGENT_REGISTRATION] Found {len(created_agents)} immediately-created agents: {list(created_agents.keys())}"
        )
        for agent_name, agent_primitive in created_agents.items():
            self.agents[agent_name] = agent_primitive
            logger.info(
                f"[AGENT_REGISTRATION] Registered immediately-created agent '{agent_name}' in runtime.agents"
            )

        # Store registries for later handle enhancement
        self._dsl_registries = stubs.pop("_registries", {})

        # Extract the binding callback for assignment interception
        binding_callback = stubs.pop("_tactus_register_binding", None)

        for name, stub in stubs.items():
            sandbox.set_global(name, stub)

        # Enable assignment interception for new syntax (Phase B+)
        # This captures assignments like: multiply = Tool {...}
        if binding_callback:
            sandbox.setup_assignment_interception(binding_callback)

        # Execute file - declarations self-register
        # Also capture the result for top-level code execution (when no Procedure blocks exist)
        try:
            execution_result = sandbox.execute(source)
            # Store result for later use if there's no main procedure
            self._top_level_result = execution_result
        except LuaSandboxError as e:
            raise TactusRuntimeError(f"Failed to parse DSL: {e}")

        # Auto-register plain function main() if it exists
        #
        # Some .tac files use plain Lua syntax: `function main() ... end`
        # instead of the Procedure DSL syntax: `Procedure { function(input) ... end }`
        #
        # For these files, we need to explicitly check lua.globals() after execution
        # and register any function named "main" as the main procedure.
        #
        # This allows both syntax styles to work:
        # 1. DSL style (self-registering): Procedure { function(input) ... end }
        # 2. Plain Lua style (auto-registered): function main() ... end
        #
        # The script mode transformation (in _maybe_transform_script_mode_source)
        # is designed to skip files with named function definitions to avoid wrapping
        # them incorrectly.
        lua_globals = sandbox.lua.globals()
        if "main" in lua_globals:
            main_func = lua_globals["main"]
            # Check if it's a function and not already registered
            if callable(main_func) and "main" not in builder.registry.named_procedures:
                logger.info(
                    "[AUTO_REGISTER] Found plain function main(), auto-registering as main procedure"
                )
                builder.register_named_procedure(
                    name="main",
                    lua_function=main_func,
                    input_schema={},
                    output_schema={},
                    state_schema={},
                )

        # Validate and return registry
        result = builder.validate()
        if not result.valid:
            error_messages = [f"  - {err.message}" for err in result.errors]
            raise TactusRuntimeError("DSL validation failed:\n" + "\n".join(error_messages))

        for warning in result.warnings:
            logger.warning(warning.message)

        logger.debug(f"Registry after parsing: lua_tools={list(result.registry.lua_tools.keys())}")
        return result.registry

    def _registry_to_config(self, registry: ProcedureRegistry) -> dict[str, Any]:
        """
        Convert registry to config dict format.

        Args:
            registry: ProcedureRegistry

        Returns:
            Config dict
        """
        config = {}

        if registry.description:
            config["description"] = registry.description

        # Convert input schema
        if registry.input_schema:
            config["input"] = registry.input_schema

        # Convert output schema
        if registry.output_schema:
            config["output"] = registry.output_schema

        # Convert state schema
        if registry.state_schema:
            config["state"] = registry.state_schema

        # Convert agents
        if registry.agents:
            config["agents"] = {}
            for name, agent in registry.agents.items():
                config["agents"][name] = {
                    "provider": agent.provider,
                    "model": agent.model,
                    "system_prompt": agent.system_prompt,
                    # Tools control tool calling availability (tool/toolset references + expressions)
                    # Keep empty list as [] (not None) to preserve "explicitly no tools" intent
                    "tools": agent.tools,
                    "max_turns": agent.max_turns,
                    "disable_streaming": agent.disable_streaming,
                }
                # Include model configuration parameters if present
                if agent.temperature is not None:
                    config["agents"][name]["temperature"] = agent.temperature
                if agent.max_tokens is not None:
                    config["agents"][name]["max_tokens"] = agent.max_tokens
                if agent.model_type is not None:
                    config["agents"][name]["model_type"] = agent.model_type
                # Include inline tool definitions if present
                if agent.inline_tools:
                    config["agents"][name]["inline_tools"] = agent.inline_tools
                if agent.initial_message:
                    config["agents"][name]["initial_message"] = agent.initial_message
                if agent.output:
                    config["agents"][name]["output_schema"] = {
                        field_name: {
                            "type": (
                                field.field_type.value
                                if hasattr(field.field_type, "value")
                                else field.field_type
                            ),
                            "required": field.required,
                        }
                        for field_name, field in agent.output.fields.items()
                    }
                if agent.message_history:
                    config["agents"][name]["message_history"] = {
                        "source": agent.message_history.source,
                        "filter": agent.message_history.filter,
                    }

        # Convert HITL points
        if registry.hitl_points:
            config["hitl"] = {}
            for name, hitl in registry.hitl_points.items():
                config["hitl"][name] = {
                    "type": hitl.hitl_type,
                    "message": hitl.message,
                }
                if hitl.timeout:
                    config["hitl"][name]["timeout"] = hitl.timeout
                if hitl.default is not None:
                    config["hitl"][name]["default"] = hitl.default
                if hitl.options:
                    config["hitl"][name]["options"] = hitl.options

        # Convert prompts
        if registry.prompts:
            config["prompts"] = registry.prompts
        if registry.return_prompt:
            config["return_prompt"] = registry.return_prompt
        if registry.error_prompt:
            config["error_prompt"] = registry.error_prompt
        if registry.status_prompt:
            config["status_prompt"] = registry.status_prompt

        # Add default provider/model
        if registry.default_provider:
            config["default_provider"] = registry.default_provider
        if registry.default_model:
            config["default_model"] = registry.default_model

        # The procedure code will be executed separately
        # Store a placeholder for compatibility
        config["procedure"] = "-- Procedure function stored in registry"

        return config

    def _create_runtime_for_procedure(
        self, procedure_name: str, params: dict[str, Any]
    ) -> "TactusRuntime":
        """
        Create a new runtime instance for a sub-procedure.

        Args:
            procedure_name: Name or path of the procedure to load
            params: Parameters to pass to the procedure

        Returns:
            New TactusRuntime instance
        """
        # Generate unique ID for sub-procedure
        sub_procedure_id = f"{self.procedure_id}_{procedure_name}_{uuid.uuid4().hex[:8]}"

        # Create new runtime with incremented depth
        runtime = TactusRuntime(
            procedure_id=sub_procedure_id,
            storage_backend=self.storage_backend,
            hitl_handler=self.hitl_handler,
            chat_recorder=self.chat_recorder,
            mcp_server=self.mcp_server,
            openai_api_key=self.openai_api_key,
            log_handler=self.log_handler,
            recursion_depth=self.recursion_depth + 1,
        )

        logger.info(
            f"Created runtime for sub-procedure '{procedure_name}' "
            f"(depth {self.recursion_depth + 1})"
        )

        return runtime

    def _load_procedure_by_name(self, name: str) -> str:
        """
        Load procedure source code by name.

        Args:
            name: Procedure name or file path

        Returns:
            Procedure source code

        Raises:
            FileNotFoundError: If procedure file not found
        """
        import os

        # Try different locations
        search_paths = [
            name,  # Exact path
            f"{name}.tac",  # Add extension
            f"examples/{name}",  # Examples directory
            f"examples/{name}.tac",  # Examples with extension
        ]

        for path in search_paths:
            if os.path.exists(path):
                logger.debug(f"Loading procedure from: {path}")
                with open(path, "r") as f:
                    return f.read()

        raise FileNotFoundError(f"Procedure '{name}' not found. Searched: {search_paths}")
