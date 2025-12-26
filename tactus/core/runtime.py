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
from typing import Dict, Any, Optional

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
from tactus.primitives.stage import StagePrimitive
from tactus.primitives.json import JsonPrimitive
from tactus.primitives.retry import RetryPrimitive
from tactus.primitives.file import FilePrimitive
from tactus.primitives.procedure import ProcedurePrimitive

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
        storage_backend: Optional[StorageBackend] = None,
        hitl_handler: Optional[HITLHandler] = None,
        chat_recorder: Optional[ChatRecorder] = None,
        mcp_server=None,
        mcp_servers: Optional[Dict[str, Any]] = None,
        openai_api_key: Optional[str] = None,
        log_handler=None,
        tool_primitive: Optional[ToolPrimitive] = None,
        skip_agents: bool = False,
        recursion_depth: int = 0,
        tool_paths: Optional[list] = None,
        external_config: Optional[Dict[str, Any]] = None,
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
            skip_agents: If True, skip agent setup and execution (for testing)
            tool_paths: Optional list of paths to scan for local Python tool plugins
            external_config: Optional external config (from .tac.yml) to merge with DSL config
        """
        self.procedure_id = procedure_id
        self.storage_backend = storage_backend
        self.hitl_handler = hitl_handler
        self.chat_recorder = chat_recorder
        self.mcp_server = mcp_server  # Keep for backward compatibility
        self.mcp_servers = mcp_servers or {}
        self.mcp_manager = None  # Will be initialized in _setup_agents
        self.openai_api_key = openai_api_key
        self.log_handler = log_handler
        self._injected_tool_primitive = tool_primitive
        self.tool_paths = tool_paths or []
        self.skip_agents = skip_agents
        self.recursion_depth = recursion_depth
        self.external_config = external_config or {}

        # Will be initialized during setup
        self.config: Optional[Dict[str, Any]] = None  # Legacy YAML support
        self.registry: Optional[ProcedureRegistry] = None  # New DSL registry
        self.lua_sandbox: Optional[LuaSandbox] = None
        self.output_validator: Optional[OutputValidator] = None
        self.template_resolver: Optional[TemplateResolver] = None
        self.message_history_manager: Optional[MessageHistoryManager] = None

        # Execution context
        self.execution_context: Optional[BaseExecutionContext] = None

        # Primitives (shared across all agents)
        self.state_primitive: Optional[StatePrimitive] = None
        self.iterations_primitive: Optional[IterationsPrimitive] = None
        self.stop_primitive: Optional[StopPrimitive] = None
        self.tool_primitive: Optional[ToolPrimitive] = None
        self.human_primitive: Optional[HumanPrimitive] = None
        self.step_primitive: Optional[StepPrimitive] = None
        self.checkpoint_primitive: Optional[CheckpointPrimitive] = None
        self.log_primitive: Optional[LogPrimitive] = None
        self.stage_primitive: Optional[StagePrimitive] = None
        self.json_primitive: Optional[JsonPrimitive] = None
        self.retry_primitive: Optional[RetryPrimitive] = None
        self.file_primitive: Optional[FilePrimitive] = None
        self.procedure_primitive: Optional[ProcedurePrimitive] = None

        # Agent primitives (one per agent)
        self.agents: Dict[str, Any] = {}

        # Model primitives (one per model)
        self.models: Dict[str, Any] = {}

        # Toolset registry (name -> AbstractToolset instance)
        self.toolset_registry: Dict[str, Any] = {}

        # User dependencies (HTTP clients, DB connections, etc.)
        self.user_dependencies: Dict[str, Any] = {}
        self.dependency_manager: Optional[Any] = None  # ResourceManager for cleanup

        logger.info(f"TactusRuntime initialized for procedure {procedure_id}")

    async def execute(
        self, source: str, context: Optional[Dict[str, Any]] = None, format: str = "yaml"
    ) -> Dict[str, Any]:
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
        session_id = None
        self.context = context or {}  # Store context for param merging

        try:
            # 0. Setup Lua sandbox FIRST (needed for both YAML and Lua DSL)
            logger.info("Step 0: Setting up Lua sandbox")
            self.lua_sandbox = LuaSandbox()

            # 0b. For Lua DSL, inject placeholder primitives BEFORE parsing
            # so they're available in the procedure function's closure
            if format == "lua":
                logger.debug("Pre-injecting placeholder primitives for Lua DSL parsing")
                # Import here to avoid issues with YAML format
                from tactus.primitives.log import LogPrimitive as LuaLogPrimitive
                from tactus.primitives.state import StatePrimitive as LuaStatePrimitive
                from tactus.primitives.tool import ToolPrimitive as LuaToolPrimitive

                # Create minimal primitives that don't need full config
                placeholder_log = LuaLogPrimitive(procedure_id=self.procedure_id)
                placeholder_state = LuaStatePrimitive()
                placeholder_tool = LuaToolPrimitive()
                placeholder_params = {}  # Empty params dict
                self.lua_sandbox.inject_primitive("Log", placeholder_log)
                self.lua_sandbox.inject_primitive("State", placeholder_state)  # Capital S
                self.lua_sandbox.inject_primitive("state", placeholder_state)  # lowercase s
                self.lua_sandbox.inject_primitive("Tool", placeholder_tool)
                self.lua_sandbox.inject_primitive("params", placeholder_params)

            # 1. Parse configuration (Lua DSL or YAML)
            if format == "lua":
                logger.info("Step 1: Parsing Lua DSL configuration")
                self.registry = self._parse_declarations(source)
                logger.info("Loaded procedure from Lua DSL")
                # Convert registry to config dict for compatibility
                self.config = self._registry_to_config(self.registry)

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

                    logger.debug(f"Merged external config with {len(self.external_config)} keys")
            else:
                # Legacy YAML support
                logger.info("Step 1: Parsing YAML configuration (legacy)")
                if ProcedureYAMLParser is None:
                    raise TactusRuntimeError("YAML support not available - use Lua DSL format")
                self.config = ProcedureYAMLParser.parse(source)
                logger.info(f"Loaded procedure: {self.config['name']} v{self.config['version']}")

            # 2. Setup output validator
            logger.info("Step 2: Setting up output validator")
            output_schema = self.config.get("outputs", {})
            self.output_validator = OutputValidator(output_schema)
            if output_schema:
                logger.info(
                    f"Output schema has {len(output_schema)} fields: {list(output_schema.keys())}"
                )

            # 3. Lua sandbox is already set up in step 0
            # (keeping this comment for step numbering consistency)

            # 4. Initialize primitives
            logger.info("Step 4: Initializing primitives")
            await self._initialize_primitives()

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
                session_id = await self.chat_recorder.start_session(context)
                if session_id:
                    logger.info(f"Chat session started: {session_id}")
                else:
                    logger.warning("Failed to create chat session - continuing without recording")

            # 6. Create execution context
            logger.info("Step 6: Creating execution context")
            self.execution_context = BaseExecutionContext(
                procedure_id=self.procedure_id,
                storage_backend=self.storage_backend,
                hitl_handler=self.hitl_handler,
            )
            logger.debug("BaseExecutionContext created")

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
            declared_stages = self.config.get("stages", [])
            self.stage_primitive = StagePrimitive(
                declared_stages=declared_stages, lua_sandbox=self.lua_sandbox
            )
            self.json_primitive = JsonPrimitive(lua_sandbox=self.lua_sandbox)
            self.retry_primitive = RetryPrimitive()
            self.file_primitive = FilePrimitive()

            # Initialize Procedure primitive (requires execution_context)
            max_depth = self.config.get("max_depth", 5) if self.config else 5
            self.procedure_primitive = ProcedurePrimitive(
                execution_context=self.execution_context,
                runtime_factory=self._create_runtime_for_procedure,
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
                logger.info(f"Return prompt specified: {return_prompt[:50]}...")
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
            if self.chat_recorder and session_id:
                await self.chat_recorder.end_session(session_id, status="COMPLETED")

            # 14. Build final results
            final_state = self.state_primitive.all() if self.state_primitive else {}
            tools_used = (
                [call.name for call in self.tool_primitive.get_all_calls()]
                if self.tool_primitive
                else []
            )

            logger.info(
                f"Workflow execution complete: "
                f"{self.iterations_primitive.current() if self.iterations_primitive else 0} iterations, "
                f"{len(tools_used)} tool calls"
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
                "session_id": session_id,
                "total_cost": total_cost,
                "total_tokens": total_tokens,
                "cost_breakdown": cost_breakdown,
            }

        except ProcedureWaitingForHuman as e:
            logger.info(f"Procedure waiting for human: {e}")

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
                "session_id": session_id,
            }

        except ProcedureConfigError as e:
            logger.error(f"Configuration error: {e}")
            # Flush recordings even on error
            if self.chat_recorder and session_id:
                try:
                    await self.chat_recorder.end_session(session_id, status="FAILED")
                except Exception as err:
                    logger.warning(f"Failed to end chat session: {err}")

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
            logger.error(f"Lua execution error: {e}")

            # Apply error_prompt if specified (future: inject to agent for explanation)
            if self.config and self.config.get("error_prompt"):
                error_prompt = self.config["error_prompt"]
                logger.info(f"Error prompt specified: {error_prompt[:50]}...")
                # TODO: In full implementation, inject this prompt to an agent to get an explanation

            # Flush recordings even on error
            if self.chat_recorder and session_id:
                try:
                    await self.chat_recorder.end_session(session_id, status="FAILED")
                except Exception as err:
                    logger.warning(f"Failed to end chat session: {err}")

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
            logger.error(f"Unexpected error: {e}", exc_info=True)

            # Apply error_prompt if specified (future: inject to agent for explanation)
            if self.config and self.config.get("error_prompt"):
                error_prompt = self.config["error_prompt"]
                logger.info(f"Error prompt specified: {error_prompt[:50]}...")
                # TODO: In full implementation, inject this prompt to an agent to get an explanation

            # Flush recordings even on error
            if self.chat_recorder and session_id:
                try:
                    await self.chat_recorder.end_session(session_id, status="FAILED")
                except Exception as err:
                    logger.warning(f"Failed to end chat session: {err}")

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
                    logger.warning(f"Error disconnecting from MCP servers: {e}")

            # Cleanup: Close user dependencies
            if self.dependency_manager:
                try:
                    await self.dependency_manager.cleanup()
                    logger.info("Cleaned up user dependencies")
                except Exception as e:
                    logger.warning(f"Error cleaning up dependencies: {e}")

    async def _initialize_primitives(self):
        """Initialize all primitive objects."""
        # Get state schema from registry if available
        state_schema = self.registry.state_schema if self.registry else {}
        self.state_primitive = StatePrimitive(state_schema=state_schema)
        self.iterations_primitive = IterationsPrimitive()
        self.stop_primitive = StopPrimitive()

        # Use injected tool primitive if provided (for testing with mocks)
        if self._injected_tool_primitive:
            self.tool_primitive = self._injected_tool_primitive
            logger.info("Using injected tool primitive (mock mode)")
        else:
            self.tool_primitive = ToolPrimitive()

        # Initialize toolset primitive (needs runtime reference for resolution)
        from tactus.primitives.toolset import ToolsetPrimitive

        self.toolset_primitive = ToolsetPrimitive(runtime=self)

        logger.debug("All primitives initialized")

    def resolve_toolset(self, name: str) -> Optional[Any]:
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
            logger.warning(f"Toolset '{name}' not found in registry")
            return None

    async def _initialize_toolsets(self):
        """
        Load and register all toolsets from config and built-in sources.

        This method:
        1. Registers built-in toolsets (like "done")
        2. Loads config-defined toolsets from YAML
        3. Registers MCP toolsets by server name
        4. Registers plugin toolset if tool_paths configured
        """
        from pydantic_ai.toolsets import FunctionToolset

        # 1. Register built-in "done" toolset (always available)
        try:
            # Create done function that integrates with tool_primitive and stop_primitive
            def done(reason: str = "Task completed") -> str:
                """
                Signal that the agent has completed its task.

                Args:
                    reason: Explanation of what was accomplished

                Returns:
                    Confirmation message
                """
                # Record the tool call
                if self.tool_primitive:
                    self.tool_primitive.record_call("done", {"reason": reason}, "Done")
                    logger.debug(f"Recorded done tool call: {reason}")

                # Request stop
                if self.stop_primitive:
                    self.stop_primitive.request(reason)
                    logger.debug(f"Requested stop: {reason}")

                return f"Done: {reason}"

            builtin_done_toolset = FunctionToolset(tools=[done])
            self.toolset_registry["done"] = builtin_done_toolset
            logger.info("Registered built-in 'done' toolset")
        except Exception as e:
            logger.error(f"Failed to create built-in 'done' toolset: {e}", exc_info=True)

        # 2. Load config-defined toolsets
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

                # Get toolsets from MCP manager
                mcp_toolsets = self.mcp_manager.get_toolsets()

                # Register each MCP toolset by server name
                for server_name in self.mcp_servers.keys():
                    # Find corresponding toolset (assumes same order)
                    # TODO: MCPServerManager should provide get_named_toolsets() method
                    if mcp_toolsets:
                        # For now, register first toolset with server name
                        # This needs improvement when we add get_named_toolsets()
                        toolset = mcp_toolsets[0] if len(mcp_toolsets) == 1 else None
                        if toolset:
                            self.toolset_registry[server_name] = toolset
                            logger.info(f"Registered MCP toolset '{server_name}'")

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

        # 5. Register DSL-defined toolsets from registry
        if hasattr(self, "registry") and self.registry and hasattr(self.registry, "toolsets"):
            for name, definition in self.registry.toolsets.items():
                try:
                    toolset = await self._create_toolset_from_config(name, definition)
                    if toolset:
                        self.toolset_registry[name] = toolset
                        logger.info(f"Registered DSL-defined toolset '{name}'")
                except Exception as e:
                    logger.error(f"Failed to create DSL toolset '{name}': {e}", exc_info=True)

        # 6. Register individual Lua tool() declarations
        if hasattr(self, "registry") and self.registry and hasattr(self.registry, "lua_tools"):
            try:
                from tactus.adapters.lua_tools import LuaToolsAdapter

                lua_adapter = LuaToolsAdapter(tool_primitive=self.tool_primitive)

                for tool_name, tool_spec in self.registry.lua_tools.items():
                    try:
                        toolset = lua_adapter.create_single_tool_toolset(tool_name, tool_spec)
                        self.toolset_registry[tool_name] = toolset
                        logger.info(f"Registered Lua tool '{tool_name}' as toolset")
                    except Exception as e:
                        logger.error(f"Failed to create Lua tool '{tool_name}': {e}", exc_info=True)
            except ImportError as e:
                logger.warning(
                    f"Could not import LuaToolsAdapter: {e} - Lua tools will not be available"
                )

        logger.info(
            f"Toolset registry initialized with {len(self.toolset_registry)} toolset(s): {list(self.toolset_registry.keys())}"
        )

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

        for proc_name, proc_def in self.registry.named_procedures.items():
            try:
                logger.debug(
                    f"Processing named procedure '{proc_name}': "
                    f"function={proc_def['function']}, type={type(proc_def['function'])}"
                )

                # Create callable wrapper
                callable_wrapper = ProcedureCallable(
                    name=proc_name,
                    procedure_function=proc_def["function"],
                    input_schema=proc_def["input_schema"],
                    output_schema=proc_def["output_schema"],
                    state_schema=proc_def["state_schema"],
                    execution_context=self.execution_context,
                    lua_sandbox=self.lua_sandbox,
                )

                # Get the old stub (if it exists) to update its registry
                try:
                    old_value = self.lua_sandbox.lua.globals()[proc_name]
                    if old_value and hasattr(old_value, "registry"):
                        # Update the stub's registry so it delegates to the real callable
                        old_value.registry[proc_name] = callable_wrapper
                except (KeyError, AttributeError):
                    # Stub doesn't exist in globals yet, that's fine
                    pass

                # Inject into Lua globals (replaces placeholder)
                self.lua_sandbox.lua.globals()[proc_name] = callable_wrapper

                logger.info(f"Registered named procedure: {proc_name}")
            except Exception as e:
                logger.error(
                    f"Failed to initialize named procedure '{proc_name}': {e}",
                    exc_info=True,
                )

        logger.info(f"Initialized {len(self.registry.named_procedures)} named procedure(s)")

    async def _create_toolset_from_config(
        self, name: str, definition: Dict[str, Any]
    ) -> Optional[Any]:
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

                lua_adapter = LuaToolsAdapter(tool_primitive=self.tool_primitive)
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
                return source_toolset.filtered(lambda ctx, tool: re.match(pattern, tool.name))
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
            logger.error(f"Unknown toolset type '{toolset_type}' for toolset '{name}'")
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
                    toolset = toolset.filtered(lambda ctx, tool: tool.name in tool_names)
                    logger.debug(f"Applied include filter to toolset '{name}': {tool_names}")

                if "exclude" in expr:
                    # Exclude specific tools
                    tool_names = set(expr["exclude"])
                    toolset = toolset.filtered(lambda ctx, tool: tool.name not in tool_names)
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

    async def _setup_agents(self, context: Dict[str, Any]):
        """
        Setup agent primitives with LLMs and tools using Pydantic AI.

        Args:
            context: Procedure context with pre-loaded data
        """
        # Initialize user dependencies first (needed by agents)
        await self._initialize_dependencies()

        # Get agent configurations
        agents_config = self.config.get("agents", {})

        if not agents_config:
            logger.info("No agents defined in configuration - skipping agent setup")
            return

        # Skip agent setup in mock mode
        if self.skip_agents:
            logger.info("Skipping agent setup (mock mode)")
            from tactus.testing.mock_agent import MockAgentPrimitive

            # Create mock agent primitives
            for agent_name in agents_config.keys():
                mock_agent = MockAgentPrimitive(agent_name, self.tool_primitive)
                self.agents[agent_name] = mock_agent
                logger.debug(f"Created mock agent: {agent_name}")

            return

        # Import agent primitive
        try:
            from tactus.primitives.agent import AgentPrimitive
            from pydantic import create_model, Field  # noqa: F401
        except ImportError as e:
            logger.warning(f"Could not import AgentPrimitive: {e} - agents will not be available")
            return

        # Get default toolsets from config (for agents that don't specify toolsets)
        default_toolset_names = self.config.get("default_toolsets", [])
        if default_toolset_names:
            logger.info(f"Default toolsets configured: {default_toolset_names}")

        # Setup each agent
        for agent_name, agent_config in agents_config.items():
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

            # Handle inline Lua function tools
            inline_tools_toolset = None
            if "inline_tool_defs" in agent_config and agent_config["inline_tool_defs"]:
                tools_spec = agent_config["inline_tool_defs"]
                # These are inline tool definitions (dicts with 'handler' key)
                if isinstance(tools_spec, list):
                    inline_tool_specs = [
                        t for t in tools_spec if isinstance(t, dict) and "handler" in t
                    ]
                    if inline_tool_specs:
                        # These are inline Lua function tools
                        try:
                            from tactus.adapters.lua_tools import LuaToolsAdapter

                            lua_adapter = LuaToolsAdapter(tool_primitive=self.tool_primitive)
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

            # Get toolsets for this agent
            # Use a sentinel value to distinguish "not present" from "present but None/empty"
            _MISSING = object()
            agent_toolsets_config = agent_config.get("toolsets", _MISSING)

            # Debug log
            logger.debug(
                f"Agent '{agent_name}' raw toolsets config: {agent_toolsets_config}, type: {type(agent_toolsets_config)}"
            )

            # Convert Lua table to Python list if needed
            if (
                agent_toolsets_config is not _MISSING
                and agent_toolsets_config is not None
                and hasattr(agent_toolsets_config, "__len__")
            ):
                try:
                    # Try to convert Lua table to list
                    agent_toolsets_config = (
                        list(agent_toolsets_config.values())
                        if hasattr(agent_toolsets_config, "values")
                        else list(agent_toolsets_config)
                    )
                    logger.debug(
                        f"Agent '{agent_name}' converted toolsets to: {agent_toolsets_config}"
                    )
                except (TypeError, AttributeError):
                    # If conversion fails, leave as-is
                    pass

            if agent_toolsets_config is _MISSING:
                # No toolsets key present - use default toolsets if configured, otherwise all
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
            elif isinstance(agent_toolsets_config, list) and len(agent_toolsets_config) == 0:
                # Explicitly empty list - no toolsets
                # Use None instead of [] to completely disable tool calling for Bedrock models
                filtered_toolsets = None
                logger.info(
                    f"Agent '{agent_name}' has NO toolsets (explicitly empty - passing None)"
                )
            else:
                # Parse toolset expressions
                filtered_toolsets = self._parse_toolset_expressions(agent_toolsets_config)
                logger.info(f"Agent '{agent_name}' toolsets: {agent_toolsets_config}")

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
            result_type = None
            output_schema_guidance = None

            # Prefer output_type (aligned with pydantic-ai)
            if agent_config.get("output_type"):
                try:
                    result_type = self._create_pydantic_model_from_output_type(
                        agent_config["output_type"], f"{agent_name}Output"
                    )
                    logger.info(f"Using agent output_type schema for '{agent_name}'")
                except Exception as e:
                    logger.warning(f"Failed to create output model from output_type: {e}")
            elif agent_config.get("output_schema"):
                # Fallback to output_schema for backward compatibility
                output_schema = agent_config["output_schema"]
                try:
                    result_type = self._create_output_model_from_schema(
                        output_schema, f"{agent_name}Output"
                    )
                    logger.info(f"Created structured output model for agent '{agent_name}'")
                except Exception as e:
                    logger.warning(f"Failed to create output model for agent '{agent_name}': {e}")
            elif self.config.get("outputs"):
                # Use procedure-level output schema
                try:
                    result_type = self._create_output_model_from_schema(
                        self.config["outputs"], f"{agent_name}Output"
                    )
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

            # Create AgentPrimitive with toolsets
            # Pass None instead of empty list for toolsets to disable tool calling entirely
            agent_primitive = AgentPrimitive(
                name=agent_name,
                system_prompt_template=system_prompt_template,
                initial_message=initial_message,
                model=model_name,
                model_settings=model_settings,
                tools=filtered_tools,  # Empty list - kept for backward compat in AgentPrimitive
                toolsets=filtered_toolsets,  # List of toolsets (may be empty)
                tool_primitive=self.tool_primitive,
                stop_primitive=self.stop_primitive,
                iterations_primitive=self.iterations_primitive,
                state_primitive=self.state_primitive,
                context=context,
                output_schema_guidance=output_schema_guidance,
                chat_recorder=self.chat_recorder,
                result_type=result_type,
                log_handler=self.log_handler,
                procedure_id=self.procedure_id,
                provider=agent_config.get("provider"),
                disable_streaming=agent_config.get("disable_streaming", False),
                message_history_filter=message_history_filter,
                user_dependencies=self.user_dependencies if self.user_dependencies else None,
                execution_context=self.execution_context,
            )

            self.agents[agent_name] = agent_primitive

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
                )

                self.models[model_name] = model_primitive
                logger.info(f"Model '{model_name}' configured successfully")

            except Exception as e:
                logger.error(f"Failed to setup model '{model_name}': {e}")
                raise

    def _create_pydantic_model_from_output_type(self, output_type_schema, model_name: str) -> type:
        """
        Convert output_type schema to Pydantic model.

        Aligned with pydantic-ai's output_type parameter.

        Args:
            output_type_schema: AgentOutputSchema or dict with field definitions
            model_name: Name for the generated Pydantic model

        Returns:
            Dynamically created Pydantic model class
        """
        from pydantic import create_model
        from typing import Optional

        fields = {}

        # Handle AgentOutputSchema object
        if hasattr(output_type_schema, "fields"):
            schema_fields = output_type_schema.fields
        else:
            # Assume it's a dict
            schema_fields = output_type_schema

        for field_name, field_def in schema_fields.items():
            # Extract field properties
            if hasattr(field_def, "type"):
                field_type_str = field_def.type
                required = getattr(field_def, "required", True)
            else:
                # Dict format
                field_type_str = field_def.get("type", "string")
                required = field_def.get("required", True)

            # Map type string to Python type
            field_type = self._map_type_string(field_type_str)

            # Create field tuple (type, default_or_required)
            if required:
                fields[field_name] = (field_type, ...)  # Required field
            else:
                fields[field_name] = (Optional[field_type], None)  # Optional field

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
        self, output_schema: Dict[str, Any], model_name: str = "OutputModel"
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

            self.lua_sandbox.set_global("input", input_values)
            logger.info(f"Injected input into Lua sandbox: {input_values}")

        # Inject shared primitives
        if self.state_primitive:
            self.lua_sandbox.inject_primitive("State", self.state_primitive)
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
            # Also inject checkpoint() as a global function for convenience
            self.lua_sandbox.inject_primitive("checkpoint", self.step_primitive.checkpoint)
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

        if self.stage_primitive:
            logger.info(f"Injecting Stage primitive: {self.stage_primitive}")

            # Create wrapper to map 'is' (reserved keyword in Python) to 'is_current'
            class StageWrapper:
                def __init__(self, stage_primitive):
                    self._stage = stage_primitive

                def __getattr__(self, name):
                    if name == "is":
                        return self._stage.is_current
                    return getattr(self._stage, name)

            stage_wrapper = StageWrapper(self.stage_primitive)
            self.lua_sandbox.inject_primitive("Stage", stage_wrapper)

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

        # Inject Sleep function
        def sleep_wrapper(seconds):
            """Sleep for specified number of seconds."""
            logger.info(f"Sleep({seconds}) - pausing execution")
            time.sleep(seconds)
            logger.info(f"Sleep({seconds}) - resuming execution")

        self.lua_sandbox.set_global("Sleep", sleep_wrapper)
        logger.info("Injected Sleep function")

        # Inject agent primitives (capitalized names)
        for agent_name, agent_primitive in self.agents.items():
            # Capitalize first letter for Lua convention (Worker, Assistant, etc.)
            lua_name = agent_name.capitalize()
            self.lua_sandbox.inject_primitive(lua_name, agent_primitive)
            logger.info(f"Injected agent primitive: {lua_name}")

        # Inject model primitives (capitalized names)
        for model_name, model_primitive in self.models.items():
            # Capitalize first letter for Lua convention (IntentClassifier, Embedder, etc.)
            lua_name = model_name.capitalize()
            self.lua_sandbox.inject_primitive(lua_name, model_primitive)
            logger.info(f"Injected model primitive: {lua_name}")

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
                    )

                    # Gather input parameters from context, applying defaults
                    input_params = {}
                    for key, field_def in main_proc["input_schema"].items():
                        # Check context first
                        if hasattr(self, "context") and self.context and key in self.context:
                            input_params[key] = self.context[key]
                        # Apply default if available and not required
                        elif isinstance(field_def, dict) and "default" in field_def:
                            input_params[key] = field_def["default"]
                        # If required and not in context, it will fail validation in ProcedureCallable

                    logger.debug(f"Calling main with input_params: {input_params}")

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
                except Exception as e:
                    logger.error(f"Named 'main' procedure execution failed: {e}")
                    raise LuaSandboxError(f"Named 'main' procedure execution failed: {e}")

            else:
                # No main procedure found
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

    def _process_template(self, template: str, context: Dict[str, Any]) -> str:
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
                    parts = field_name.split(".")
                    obj = kwargs
                    for part in parts:
                        if isinstance(obj, dict):
                            obj = obj.get(part, "")
                        else:
                            obj = getattr(obj, part, "")
                    return obj, field_name

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
            result = formatter.format(template, **template_vars)
            return result

        except KeyError as e:
            logger.warning(f"Template variable {e} not found, using template as-is")
            return template

        except Exception as e:
            logger.error(f"Error processing template: {e}")
            return template

    def _format_output_schema_for_prompt(self) -> str:
        """
        Format the output schema as guidance for LLM prompts.

        Returns:
            Formatted string describing expected outputs
        """
        outputs = self.config.get("outputs", {})
        if not outputs:
            return ""

        lines = ["## Expected Output Format", ""]
        lines.append("This workflow must return a structured result with the following fields:")
        lines.append("")

        # Format each output field
        for field_name, field_def in outputs.items():
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

    def get_state(self) -> Dict[str, Any]:
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

    def _parse_declarations(self, source: str) -> ProcedureRegistry:
        """
        Execute .tac to collect declarations.

        Args:
            source: Lua DSL source code

        Returns:
            ProcedureRegistry with all declarations

        Raises:
            TactusRuntimeError: If validation fails
        """
        builder = RegistryBuilder()

        # Use the existing sandbox so procedure functions have access to primitives
        sandbox = self.lua_sandbox

        # Inject DSL stubs
        stubs = create_dsl_stubs(builder)
        for name, stub in stubs.items():
            sandbox.set_global(name, stub)

        # Execute file - declarations self-register
        try:
            sandbox.execute(source)
        except LuaSandboxError as e:
            raise TactusRuntimeError(f"Failed to parse DSL: {e}")

        # Validate and return registry
        result = builder.validate()
        if not result.valid:
            error_messages = [f"  - {err.message}" for err in result.errors]
            raise TactusRuntimeError("DSL validation failed:\n" + "\n".join(error_messages))

        for warning in result.warnings:
            logger.warning(warning.message)

        return result.registry

    def _registry_to_config(self, registry: ProcedureRegistry) -> Dict[str, Any]:
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
            config["outputs"] = registry.output_schema

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
                    # Use toolsets instead of tools (breaking change)
                    # Keep empty list as [] (not None) to preserve "explicitly no tools" intent
                    "toolsets": agent.tools,
                    "max_turns": agent.max_turns,
                    "disable_streaming": agent.disable_streaming,
                }
                # Include inline tool definitions if present
                if hasattr(agent, "inline_tool_defs") and agent.inline_tool_defs:
                    config["agents"][name]["inline_tool_defs"] = agent.inline_tool_defs
                if agent.initial_message:
                    config["agents"][name]["initial_message"] = agent.initial_message
                if agent.output:
                    config["agents"][name]["output_schema"] = {
                        field_name: {
                            "type": field.field_type.value,
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

        # Convert stages
        if registry.stages:
            # Handle case where stages is [[list]] instead of [list]
            if len(registry.stages) == 1 and isinstance(registry.stages[0], list):
                config["stages"] = registry.stages[0]
            else:
                config["stages"] = registry.stages

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
        self, procedure_name: str, params: Dict[str, Any]
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
            skip_agents=self.skip_agents,
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
