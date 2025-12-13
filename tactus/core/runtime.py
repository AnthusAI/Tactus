"""
Tactus Runtime - Main execution engine for Lua-based workflows.

Orchestrates:
1. Lua DSL parsing and validation (via registry)
2. Lua sandbox setup
3. Primitive injection
4. Agent configuration with LLMs and tools (optional)
5. Workflow execution
"""

import logging
import time
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
        openai_api_key: Optional[str] = None,
        log_handler=None,
        tool_primitive: Optional[ToolPrimitive] = None,
        skip_agents: bool = False,
    ):
        """
        Initialize the Tactus runtime.

        Args:
            procedure_id: Unique procedure identifier
            storage_backend: Storage backend for checkpoints and state
            hitl_handler: Handler for human-in-the-loop interactions
            chat_recorder: Optional chat recorder for conversation logging
            mcp_server: Optional MCP server providing tools
            openai_api_key: Optional OpenAI API key for LLMs
            log_handler: Optional handler for structured log events
            tool_primitive: Optional pre-configured ToolPrimitive (for testing with mocks)
            skip_agents: If True, skip agent setup and execution (for testing)
        """
        self.procedure_id = procedure_id
        self.storage_backend = storage_backend
        self.hitl_handler = hitl_handler
        self.chat_recorder = chat_recorder
        self.mcp_server = mcp_server
        self.openai_api_key = openai_api_key
        self.log_handler = log_handler
        self._injected_tool_primitive = tool_primitive
        self.skip_agents = skip_agents

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

        # Agent primitives (one per agent)
        self.agents: Dict[str, Any] = {}

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
            logger.debug("HITL, checkpoint, and message history primitives initialized")

            # 8. Setup agents with LLMs and tools
            logger.info("Step 8: Setting up agents")
            # Set OpenAI API key in environment if provided (for OpenAI agents)
            import os

            if self.openai_api_key and "OPENAI_API_KEY" not in os.environ:
                os.environ["OPENAI_API_KEY"] = self.openai_api_key

            # Always set up agents - they may use providers other than OpenAI (e.g., Bedrock)
            await self._setup_agents(context or {})

            # 9. Inject primitives into Lua
            logger.info("Step 9: Injecting primitives into Lua environment")
            self._inject_primitives()

            # 10. Execute workflow (may raise ProcedureWaitingForHuman)
            logger.info("Step 10: Executing Lua workflow")
            workflow_result = self._execute_workflow()

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

            return {
                "success": False,
                "procedure_id": self.procedure_id,
                "error": f"Configuration error: {e}",
            }

        except LuaSandboxError as e:
            logger.error(f"Lua execution error: {e}")
            # Flush recordings even on error
            if self.chat_recorder and session_id:
                try:
                    await self.chat_recorder.end_session(session_id, status="FAILED")
                except Exception as err:
                    logger.warning(f"Failed to end chat session: {err}")

            return {
                "success": False,
                "procedure_id": self.procedure_id,
                "error": f"Lua execution error: {e}",
            }

        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            # Flush recordings even on error
            if self.chat_recorder and session_id:
                try:
                    await self.chat_recorder.end_session(session_id, status="FAILED")
                except Exception as err:
                    logger.warning(f"Failed to end chat session: {err}")

            return {
                "success": False,
                "procedure_id": self.procedure_id,
                "error": f"Unexpected error: {e}",
            }

    async def _initialize_primitives(self):
        """Initialize all primitive objects."""
        self.state_primitive = StatePrimitive()
        self.iterations_primitive = IterationsPrimitive()
        self.stop_primitive = StopPrimitive()

        # Use injected tool primitive if provided (for testing with mocks)
        if self._injected_tool_primitive:
            self.tool_primitive = self._injected_tool_primitive
            logger.info("Using injected tool primitive (mock mode)")
        else:
            self.tool_primitive = ToolPrimitive()

        logger.debug("All primitives initialized")

    async def _setup_agents(self, context: Dict[str, Any]):
        """
        Setup agent primitives with LLMs and tools using Pydantic AI.

        Args:
            context: Procedure context with pre-loaded data
        """
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

        # Load tools from MCP server if available
        all_pydantic_tools = []
        if self.mcp_server:
            # Connect to MCP server and get tools
            async with self.mcp_server.connect(
                {"name": f"Tactus Runtime for {self.procedure_id}"}
            ) as mcp_client:
                try:
                    from tactus.adapters.mcp import PydanticAIMCPAdapter
                except ImportError as e:
                    logger.warning(
                        f"Could not import MCP adapter: {e} - external tools will not be available"
                    )
                else:
                    # Create adapter with tool_primitive for recording
                    adapter = PydanticAIMCPAdapter(mcp_client, tool_primitive=self.tool_primitive)
                    all_pydantic_tools = await adapter.load_tools()

                    logger.info(f"Loaded {len(all_pydantic_tools)} MCP tools as Pydantic AI tools")
        else:
            logger.info("No MCP server configured - agents will only have built-in tools")

        # Prepare output schema guidance if defined
        output_schema_guidance = None
        if self.config.get("outputs"):
            output_schema_guidance = self._format_output_schema_for_prompt()
            logger.info("Prepared output schema guidance for agents")

        # Setup each agent
        for agent_name, agent_config in agents_config.items():
            logger.info(f"Setting up agent: {agent_name}")

            # Get agent prompts (initial_message needs template processing, system_prompt is dynamic)
            system_prompt_template = agent_config[
                "system_prompt"
            ]  # Keep as template for dynamic rendering
            initial_message = self._process_template(agent_config["initial_message"], context)

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

            # Filter tools for this agent
            allowed_tool_names = agent_config.get("tools", [])
            # Match tools by name (Pydantic AI Tool has a 'name' attribute)
            filtered_tools = [
                tool
                for tool in all_pydantic_tools
                if hasattr(tool, "name") and tool.name in allowed_tool_names
            ]

            logger.info(
                f"Agent '{agent_name}' has {len(filtered_tools)} tools: {allowed_tool_names}"
            )

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

            # Create AgentPrimitive
            agent_primitive = AgentPrimitive(
                name=agent_name,
                system_prompt_template=system_prompt_template,
                initial_message=initial_message,
                model=model_name,
                model_settings=model_settings,
                tools=filtered_tools,
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
            )

            self.agents[agent_name] = agent_primitive

            logger.info(f"Agent '{agent_name}' configured successfully with model '{model_name}'")

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
        # Inject params with default values, then override with context values
        if "params" in self.config:
            params_config = self.config["params"]
            param_values = {}
            # Start with defaults
            for param_name, param_def in params_config.items():
                if "default" in param_def:
                    param_values[param_name] = param_def["default"]
            # Override with context values
            for param_name in params_config.keys():
                if param_name in self.context:
                    param_values[param_name] = self.context[param_name]
            self.lua_sandbox.set_global("params", param_values)
            logger.info(f"Injected params into Lua sandbox: {param_values}")

        # Inject shared primitives
        if self.state_primitive:
            self.lua_sandbox.inject_primitive("State", self.state_primitive)
        if self.iterations_primitive:
            self.lua_sandbox.inject_primitive("Iterations", self.iterations_primitive)
        if self.stop_primitive:
            self.lua_sandbox.inject_primitive("Stop", self.stop_primitive)
        if self.tool_primitive:
            self.lua_sandbox.inject_primitive("Tool", self.tool_primitive)

        # Inject checkpoint primitives
        if self.step_primitive:
            self.lua_sandbox.inject_primitive("Step", self.step_primitive)
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

        logger.debug("All primitives injected into Lua sandbox")

    def _execute_workflow(self) -> Any:
        """
        Execute the Lua procedure code.

        Returns:
            Result from Lua procedure execution
        """
        if self.registry and self.registry.procedure_function:
            # New DSL: call the stored procedure function
            logger.debug("Executing procedure function from registry")
            try:
                # The procedure function is already a Lua function reference
                # Call it directly
                result = self.registry.procedure_function()

                # Convert Lua table result to Python dict if needed
                if result is not None and hasattr(result, "items"):
                    result = lua_table_to_dict(result)

                logger.info("Procedure execution completed successfully")
                return result
            except Exception as e:
                logger.error(f"Procedure execution failed: {e}")
                raise LuaSandboxError(f"Procedure execution failed: {e}")
        else:
            # Legacy YAML: execute procedure code string
            procedure_code = self.config["procedure"]
            logger.debug(f"Executing procedure code ({len(procedure_code)} bytes)")

            try:
                result = self.lua_sandbox.execute(procedure_code)
                logger.info("Procedure execution completed successfully")
                return result

            except LuaSandboxError as e:
                logger.error(f"Procedure execution failed: {e}")
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

            # Add params from config with default values
            if "params" in self.config:
                params = self.config["params"]
                param_values = {}
                for param_name, param_def in params.items():
                    if "default" in param_def:
                        param_values[param_name] = param_def["default"]
                template_vars["params"] = param_values

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
        Convert registry to legacy config dict format for compatibility.

        Args:
            registry: ProcedureRegistry

        Returns:
            Config dict in YAML format
        """
        config = {}

        if registry.description:
            config["description"] = registry.description

        # Convert parameters
        if registry.parameters:
            config["params"] = {}
            for name, param in registry.parameters.items():
                config["params"][name] = {
                    "type": param.parameter_type.value,
                    "required": param.required,
                }
                if param.default is not None:
                    config["params"][name]["default"] = param.default
                if param.description:
                    config["params"][name]["description"] = param.description
                if param.enum:
                    config["params"][name]["enum"] = param.enum

        # Convert outputs
        if registry.outputs:
            config["outputs"] = {}
            for name, output in registry.outputs.items():
                config["outputs"][name] = {
                    "type": output.field_type.value,
                    "required": output.required,
                }
                if output.description:
                    config["outputs"][name]["description"] = output.description

        # Convert agents
        if registry.agents:
            config["agents"] = {}
            for name, agent in registry.agents.items():
                config["agents"][name] = {
                    "provider": agent.provider,
                    "model": agent.model,
                    "system_prompt": agent.system_prompt,
                    "tools": agent.tools,
                    "max_turns": agent.max_turns,
                }
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
