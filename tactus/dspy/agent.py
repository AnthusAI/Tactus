"""
DSPy-based Agent implementation for Tactus.

This module provides an Agent implementation built on top of DSPy primitives
(Module, Signature, History, Prediction). It maintains the same external API
as the original pydantic_ai-based Agent while using DSPy for LLM interactions.

The Agent uses:
- Configurable DSPy module (default: Predict for simple pass-through, or ChainOfThought for reasoning)
- History for conversation management
- Tool handling similar to DSPy's ReAct pattern
- Unified mocking via Mocks {} primitive
"""

import asyncio
import inspect
import json
import logging
import os
import queue
import threading
import time
import uuid
from typing import Any, Dict, List, Optional

import dspy

try:
    import nest_asyncio
except ImportError:  # pragma: no cover - optional dependency
    nest_asyncio = None

from tactus.dspy.history import TactusHistory, create_history
from tactus.dspy.module import TactusModule, create_module
from tactus.dspy.prediction import TactusPrediction, wrap_prediction
from tactus.protocols.cost import CostStats, UsageStats
from tactus.protocols.result import TactusResult
from tactus.core.template_resolver import TemplateResolver
from tactus.core.message_history_manager import MessageHistoryManager
from tactus.utils.asyncio_helpers import clear_closed_event_loop

logger = logging.getLogger(__name__)


def _tool_call_name_and_args(tc: Any) -> tuple[Any, Any]:
    """Normalize tool call entries from DSPy (dict or object with name/args)."""
    if isinstance(tc, dict):
        return tc["name"], tc.get("args")
    name = getattr(tc, "name", None)
    args = getattr(tc, "args", None)
    if name is None:
        raise TypeError(f"Unrecognized tool call shape: {type(tc)!r}")
    return name, args


def _tool_call_id_for_history(tc: Any) -> str:
    """Stable unique id for OpenAI tool rounds; reuse provider id when present."""
    if isinstance(tc, dict):
        tid = tc.get("id")
        if tid:
            return str(tid)
    tid = getattr(tc, "id", None)
    if tid:
        return str(tid)
    return f"call_{uuid.uuid4().hex}"


def _run_coroutine_sync(coro):
    """Run an async coroutine from sync code while handling nested loops."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        clear_closed_event_loop()
        return asyncio.run(coro)

    if nest_asyncio:
        nest_asyncio.apply(loop)
        return asyncio.run(coro)

    thread_result = {"value": None, "exception": None}

    def _run_in_thread():
        try:
            thread_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(thread_loop)
            try:
                thread_result["value"] = thread_loop.run_until_complete(coro)
            finally:
                thread_loop.close()
        except Exception as error:
            thread_result["exception"] = error

    worker = threading.Thread(target=_run_in_thread)
    worker.start()
    worker.join()
    if thread_result["exception"]:
        raise thread_result["exception"]
    return thread_result["value"]


def _import_pydantic_ai_tooling():
    """Lazily import Pydantic AI runtime helpers."""
    from pydantic_ai import RunContext
    from pydantic_ai.models.test import TestModel
    from pydantic_ai.usage import RunUsage

    return RunContext, TestModel, RunUsage


def _normalize_model_for_litellm(model: Optional[str], provider: Optional[str]) -> Optional[str]:
    """
    Normalize Agent model/provider configuration to LiteLLM's expected format.

    Supported inputs:
    - model="openai/gpt-4o-mini" (already normalized)
    - model="openai:gpt-4o-mini" (colon provider separator -> slash)
    - provider="openai", model="gpt-4o-mini" (combine to "openai/gpt-4o-mini")

    Note: Some provider model IDs (e.g., Bedrock) may contain ':' as part of the model ID
    (version suffix). If provider is provided and the model does not start with
    "<provider>:", we treat ':' as part of the model ID (do not rewrite).
    """
    if not model:
        return None

    normalized = model

    # Convert "provider:model" to "provider/model", but do not rewrite colons that
    # are part of a model ID (e.g., Bedrock version suffixes) unless they look like
    # an explicit provider separator.
    if ":" in normalized and "/" not in normalized:
        prefix = normalized.split(":", 1)[0]
        if provider is None or prefix == provider:
            normalized = normalized.replace(":", "/", 1)

    # Combine split provider + model into provider/model.
    if provider and "/" not in normalized:
        normalized = f"{provider}/{normalized}"

    return normalized


class DSPyAgentHandle:
    """
    A DSPy-based Agent handle that provides the callable interface.

    This is a drop-in replacement for the pydantic_ai AgentHandle,
    using DSPy primitives for LLM interactions.

    Example usage in Lua:
        worker = Agent {
            system_prompt = "You are a helpful assistant",
            tools = {search, calculator}
        }

        -- Call the agent directly
        worker()
        worker({message = input.query})
    """

    def __init__(
        self,
        name: str,
        system_prompt: str = "",
        model: Optional[str] = None,
        provider: Optional[str] = None,
        tools: Optional[List[Any]] = None,
        toolsets: Optional[List[str]] = None,
        input_schema: Optional[Dict[str, Any]] = None,
        output_schema: Optional[Dict[str, Any]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        model_type: Optional[str] = None,
        module: str = "Raw",
        initial_message: Optional[str] = None,
        registry: Any = None,
        mock_manager: Any = None,
        log_handler: Any = None,
        disable_streaming: bool = False,
        execution_context: Any = None,
        context_name: Optional[str] = None,
        **kwargs: Any,
    ):
        """
        Initialize a DSPy-based Agent.

        Args:
            name: Agent name (used for tracking/logging)
            system_prompt: System prompt for the agent
            model: Model name (in LiteLLM format, e.g., "openai/gpt-4o")
            provider: Provider name (deprecated, use model instead)
            tools: List of tools available to the agent
            toolsets: List of toolset names to include
            input_schema: Optional input schema for validation (default: {message: string})
            output_schema: Optional output schema for validation (default: {response: string})
            temperature: Model temperature; None lets configure_lm use model defaults
                (0.0 for most models; GPT-5 family omits the parameter).
            max_tokens: Maximum tokens for response
            model_type: Model type for DSPy (e.g., "chat", "responses" for reasoning models)
            module: DSPy module type to use (default: "Raw", case-insensitive). Options:
                - "Raw": Minimal formatting, direct LM calls (lowest token overhead)
                - "Predict": Simple pass-through prediction (no reasoning traces)
                - "ChainOfThought": Adds step-by-step reasoning before response
            initial_message: Initial message to send on first turn if no inject
            registry: Optional Registry instance for accessing mocks
            mock_manager: Optional MockManager instance for checking mocks
            log_handler: Optional log handler for emitting streaming events
            disable_streaming: If True, disable streaming even when log_handler is present
            execution_context: Optional ExecutionContext for checkpointing agent calls
            **kwargs: Additional configuration
        """
        self.name = name
        self.system_prompt = system_prompt
        self.model = model
        self.provider = provider
        self.tools = tools or []
        self.toolsets = toolsets or []
        self.execution_context = execution_context
        self.context_name = context_name
        self._dspy_tools_cache = None  # Cache for converted DSPy tools
        # Default input schema: {message: string}
        self.input_schema = input_schema or {"message": {"type": "string", "required": False}}
        # Default output schema: {response: string}
        self._explicit_output_schema = output_schema is not None
        self.output_schema = output_schema or {"response": {"type": "string", "required": False}}
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.model_type = model_type
        self.module = module
        self.initial_message = initial_message
        self.registry = registry
        self.mock_manager = mock_manager
        self.log_handler = log_handler
        self.disable_streaming = disable_streaming
        self.tool_choice = kwargs.get("tool_choice")  # Extract tool_choice from kwargs
        self.prepare = kwargs.get("prepare")
        self.message_history_filter = kwargs.get("message_history_filter") or kwargs.get("filter")
        response_config = kwargs.get("response") or {}
        self.response_retries = int(response_config.get("retries", 0) or 0)
        self.response_retry_delay = float(response_config.get("retry_delay", 0.0) or 0.0)
        self.kwargs = kwargs

        logger.debug(
            f"[AGENT_INIT] Agent '{self.name}' initialized with log_handler={log_handler is not None}, "
            f"disable_streaming={disable_streaming}, "
            f"log_handler_type={type(log_handler).__name__ if log_handler else 'None'}, "
            f"tool_choice={self.tool_choice}, "
            f"kwargs_keys={list(kwargs.keys())}"
        )

        # Initialize conversation history
        self._history = create_history()
        self._prepared: dict[str, Any] = {}

        # Track conversation state
        self._turn_count = 0

        # Cumulative cost/usage stats (monotonic across turns)
        self._cumulative_usage = UsageStats()
        self._cumulative_cost = CostStats()

        # Build the internal DSPy module
        self._module = self._build_module()

    @property
    def usage(self) -> UsageStats:
        """Return cumulative token usage incurred by this agent so far."""
        return self._cumulative_usage

    def cost(self) -> CostStats:
        """Return cumulative cost incurred by this agent so far."""
        return self._cumulative_cost

    def _add_usage_and_cost(self, usage_stats: UsageStats, cost_stats: CostStats) -> None:
        """Accumulate a per-call UsageStats/CostStats into agent totals."""
        self._cumulative_usage.prompt_tokens += usage_stats.prompt_tokens
        self._cumulative_usage.completion_tokens += usage_stats.completion_tokens
        self._cumulative_usage.total_tokens += usage_stats.total_tokens

        self._cumulative_cost.total_cost += cost_stats.total_cost
        self._cumulative_cost.prompt_cost += cost_stats.prompt_cost
        self._cumulative_cost.completion_cost += cost_stats.completion_cost

        # Preserve "latest known" model/provider for introspection
        if cost_stats.model:
            self._cumulative_cost.model = cost_stats.model
        if cost_stats.provider:
            self._cumulative_cost.provider = cost_stats.provider

    def _extract_last_call_stats(self) -> tuple[UsageStats, CostStats]:
        """
        Extract usage+cost from DSPy's LM history for the most recent call.

        Returns zeroed stats if no LM history is available (e.g., mocked calls).
        """
        # Default to zero (e.g., mocks or no LM configured)
        usage_stats = UsageStats()
        cost_stats = CostStats()

        lm = dspy.settings.lm
        if lm is None or not hasattr(lm, "history") or not lm.history:
            return usage_stats, cost_stats

        last_call = lm.history[-1]

        # Usage
        usage = last_call.get("usage", {}) or {}
        prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
        completion_tokens = int(usage.get("completion_tokens", 0) or 0)
        total_tokens = int(usage.get("total_tokens", 0) or 0)
        usage_stats = UsageStats(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )

        # Model/provider
        model = last_call.get("model", self.model or None)
        provider = None
        if model and "/" in str(model):
            provider = str(model).split("/")[0]

        # Cost: prefer the history value, fallback to hidden params / LiteLLM calc
        total_cost = last_call.get("cost")
        if total_cost is None:
            response = last_call.get("response")
            if response and hasattr(response, "_hidden_params"):
                total_cost = response._hidden_params.get("response_cost")

            if total_cost is None and total_tokens > 0:
                try:
                    # We already have token counts, so compute cost from tokens to avoid relying
                    # on provider-specific response object shapes.
                    from litellm.cost_calculator import cost_per_token

                    prompt_cost, completion_cost = cost_per_token(
                        model=str(model) if model is not None else "",
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        call_type="completion",
                    )
                    total_cost = float(prompt_cost) + float(completion_cost)
                except Exception as e:
                    logger.warning(f"[COST] Agent '{self.name}': failed to calculate cost: {e}")
                    total_cost = 0.0
            elif total_cost is None:
                total_cost = 0.0

        total_cost = float(total_cost or 0.0)

        # Approximate prompt/completion split by token ratio
        if total_tokens > 0 and total_cost > 0:
            prompt_cost = total_cost * (prompt_tokens / total_tokens)
            completion_cost = total_cost * (completion_tokens / total_tokens)
        else:
            prompt_cost = 0.0
            completion_cost = 0.0

        cost_stats = CostStats(
            total_cost=total_cost,
            prompt_cost=prompt_cost,
            completion_cost=completion_cost,
            model=str(model) if model is not None else None,
            provider=provider,
        )

        return usage_stats, cost_stats

    def _prediction_to_value(self, prediction: TactusPrediction) -> Any:
        """
        Convert a Prediction into a stable `result.output`.

        Default behavior:
        - Prefer the `response` field when present (string)
        - Otherwise fall back to `prediction.message`
        - If an output schema is configured, attempt to parse JSON into a dict/list
        - If multiple output fields exist, return a dict (excluding internal fields)
        """
        try:
            data = prediction.data()
        except Exception:
            data = {}

        filtered = {k: v for k, v in data.items() if k not in {"tool_calls"}}

        if "response" in filtered and isinstance(filtered["response"], str) and len(filtered) <= 1:
            text = filtered["response"]
        else:
            text = prediction.message

        # If output schema is configured, prefer structured JSON when possible
        if self.output_schema and isinstance(text, str) and text.strip():
            try:
                parsed = json.loads(text)
                return parsed
            except Exception:
                pass

        # If multiple non-internal output fields exist, return structured dict
        if len(filtered) > 1:
            return filtered

        if len(filtered) == 1:
            return next(iter(filtered.values()))

        return text

    def _wrap_as_result(
        self, prediction: TactusPrediction, usage_stats: UsageStats, cost_stats: CostStats
    ) -> TactusResult:
        """Wrap a Prediction into the standard TactusResult."""
        return TactusResult(
            output=self._prediction_to_value(prediction),
            usage=usage_stats,
            cost_stats=cost_stats,
        )

    def _module_to_strategy(self, module: str) -> str:
        """
        Map DSPy module name to internal strategy name.

        Args:
            module: DSPy module name (e.g., "Predict", "ChainOfThought")

        Returns:
            Internal strategy name for create_module()

        Raises:
            ValueError: If module name is not recognized
        """
        mapping = {
            "predict": "predict",
            "chainofthought": "chain_of_thought",
            "raw": "raw",
            # Future modules can be added here:
            # "react": "react",
            # "programofthought": "program_of_thought",
        }
        strategy = mapping.get(module.lower())
        if strategy is None:
            raise ValueError(f"Unknown module '{module}'. Supported: {list(mapping.keys())}")
        return strategy

    def _convert_toolsets_to_dspy_tools_sync(self) -> list:
        """
        Convert Pydantic AI toolsets to DSPy Tool objects (synchronous version).

        DSPy uses dspy.adapters.types.tool.Tool for native function calling.
        Pydantic AI toolsets expose tools via .get_tools(ctx) method.

        Returns:
            List of DSPy Tool objects
        """
        try:
            from dspy.adapters.types.tool import Tool as DSPyTool
        except ImportError:
            logger.error("Cannot import DSPyTool - DSPy installation may be incomplete")
            return []

        logger.debug(f"Agent '{self.name}' has {len(self.toolsets)} toolsets to convert")

        dspy_tools = []

        # Convert toolsets to DSPy Tools
        for idx, toolset in enumerate(self.toolsets):
            logger.debug(f"Agent '{self.name}' processing toolset {idx}: {type(toolset).__name__}")
            try:

                # Pydantic AI FunctionToolset has a .tools dict attribute that's directly accessible
                # This avoids the need for async get_tools() call and RunContext
                if hasattr(toolset, "tools") and isinstance(toolset.tools, dict):
                    pydantic_tools = list(toolset.tools.values())
                    logger.debug(
                        f"Agent '{self.name}' toolset {idx} has {len(pydantic_tools)} tools (from .tools attribute)"
                    )
                elif hasattr(toolset, "get_tools"):
                    try:
                        RunContext, TestModel, RunUsage = _import_pydantic_ai_tooling()

                        ctx = RunContext(deps=None, model=TestModel(), usage=RunUsage())
                        tools_dict = _run_coroutine_sync(toolset.get_tools(ctx))
                        pydantic_tools = list(tools_dict.values())
                        logger.debug(
                            f"Agent '{self.name}' toolset {idx} has {len(pydantic_tools)} tools (from get_tools)"
                        )
                    except Exception as e:
                        logger.warning(f"Toolset {toolset} get_tools() failed: {e}")
                        continue
                else:
                    logger.warning(
                        f"Toolset {toolset} doesn't have accessible .tools dict, skipping"
                    )
                    continue

                for pydantic_tool in pydantic_tools:
                    if hasattr(pydantic_tool, "function_schema") and hasattr(
                        pydantic_tool.function_schema, "json_schema"
                    ):
                        # Pydantic AI Tool has: name, description, function_schema.json_schema, function
                        logger.debug(
                            f"Agent '{self.name}' converting tool: name={pydantic_tool.name}, desc={pydantic_tool.description[:50] if pydantic_tool.description else 'N/A'}..."
                        )

                        # Extract parameter schema from Pydantic AI tool
                        tool_args = None
                        json_schema = pydantic_tool.function_schema.json_schema
                        if "properties" in json_schema and json_schema["properties"]:
                            # Convert JSON schema properties to DSPy's expected format
                            tool_args = json_schema["properties"]
                        # Fallback: MCP-bridged tools use **kwargs wrappers which
                        # produce empty function_schema properties.  The original
                        # MCP input_schema is stashed by PydanticAIMCPAdapter.
                        if not tool_args and hasattr(pydantic_tool, "_mcp_input_schema"):
                            mcp_schema = pydantic_tool._mcp_input_schema
                            if isinstance(mcp_schema, dict) and mcp_schema.get("properties"):
                                tool_args = mcp_schema["properties"]
                        logger.debug(
                            f"Extracted parameter schema for '{pydantic_tool.name}': {tool_args}"
                        )

                        dspy_tool = DSPyTool(
                            func=pydantic_tool.function,
                            name=pydantic_tool.name,
                            desc=pydantic_tool.description,
                            args=tool_args,  # Pass the parameter schema
                        )
                        dspy_tools.append(dspy_tool)
                        logger.debug(
                            f"Converted tool '{pydantic_tool.name}' to DSPy Tool with args={tool_args}"
                        )
                    elif hasattr(pydantic_tool, "tool_def"):
                        tool_def = pydantic_tool.tool_def
                        tool_name = tool_def.name
                        tool_desc = tool_def.description or ""
                        tool_args = None
                        if isinstance(tool_def.parameters_json_schema, dict):
                            tool_args = tool_def.parameters_json_schema.get("properties")

                        def _make_mcp_wrapper(ts, name):
                            async def _call(**kwargs):
                                return await ts.call_tool(name, kwargs)

                            return _call

                        logger.debug(
                            f"Agent '{self.name}' converting MCP tool: name={tool_name}, desc={tool_desc[:50] if tool_desc else 'N/A'}..."
                        )
                        dspy_tool = DSPyTool(
                            func=_make_mcp_wrapper(pydantic_tool.toolset, tool_name),
                            name=tool_name,
                            desc=tool_desc,
                            args=tool_args,
                        )
                        dspy_tools.append(dspy_tool)
                        logger.debug(
                            f"Converted MCP tool '{tool_name}' to DSPy Tool with args={tool_args}"
                        )
                    elif hasattr(pydantic_tool, "name") and hasattr(pydantic_tool, "function"):
                        tool_name = pydantic_tool.name
                        tool_desc = getattr(pydantic_tool, "description", None)
                        dspy_tool = DSPyTool(
                            func=pydantic_tool.function,
                            name=tool_name,
                            desc=tool_desc,
                            args=None,
                        )
                        dspy_tools.append(dspy_tool)
                        logger.debug(f"Converted tool '{tool_name}' to DSPy Tool with args=None")
                    else:
                        logger.warning(
                            f"Skipping tool with unsupported type: {type(pydantic_tool)}"
                        )

            except Exception as e:
                import traceback

                logger.error(f"Failed to convert toolset {toolset} to DSPy Tools: {e}")
                logger.error(f"Traceback: {traceback.format_exc()}")

        logger.debug(f"Agent '{self.name}' converted {len(dspy_tools)} tools to DSPy format")
        return dspy_tools

    def _execute_tool(self, tool_name: str, tool_args: Dict[str, Any]) -> Any:
        """
        Execute a tool call using the available toolsets.

        Args:
            tool_name: Name of the tool to execute
            tool_args: Arguments to pass to the tool

        Returns:
            Tool execution result
        """
        logger.debug(f"[TOOL_EXEC] Executing tool '{tool_name}' with args: {tool_args}")

        # Emit a start event so the UI can show an in-progress tool call component
        # while the tool is executing (especially important for long-running tools).
        if self.log_handler is not None:
            try:
                from tactus.protocols.models import ToolCallStartedEvent

                tool_primitive = getattr(self, "_tool_primitive", None)
                procedure_id = (
                    getattr(tool_primitive, "procedure_id", None) if tool_primitive else None
                )
                self.log_handler.log(
                    ToolCallStartedEvent(
                        agent_name=self.name,
                        tool_name=tool_name,
                        tool_args=tool_args,
                        procedure_id=procedure_id,
                    )
                )
            except Exception as _e:
                logger.debug(f"[TOOL_EXEC] Could not emit ToolCallStartedEvent: {_e}")

        # Find the tool in our toolsets
        for toolset in self.toolsets:
            if hasattr(toolset, "tools") and isinstance(toolset.tools, dict):
                for pydantic_tool in toolset.tools.values():
                    if pydantic_tool.name == tool_name:
                        logger.debug(f"[TOOL_EXEC] Found tool '{tool_name}' in toolset")
                        try:
                            if inspect.iscoroutinefunction(pydantic_tool.function):
                                logger.debug(
                                    f"[TOOL_EXEC] Tool '{tool_name}' is async, running with nest_asyncio"
                                )
                                result = _run_coroutine_sync(pydantic_tool.function(**tool_args))
                            else:
                                # Function is sync - just call it
                                logger.debug(
                                    f"[TOOL_EXEC] Tool '{tool_name}' is sync, calling directly"
                                )
                                result = pydantic_tool.function(**tool_args)

                            logger.debug(f"[TOOL_EXEC] Tool '{tool_name}' returned: {result}")
                            return result
                        except Exception as e:
                            logger.error(
                                f"[TOOL_EXEC] Tool '{tool_name}' execution failed: {e}",
                                exc_info=True,
                            )
                            return {"error": str(e)}
            elif hasattr(toolset, "call_tool"):
                logger.debug(f"[TOOL_EXEC] Attempting MCP tool '{tool_name}' via toolset")
                try:
                    RunContext, TestModel, RunUsage = _import_pydantic_ai_tooling()

                    if inspect.iscoroutinefunction(toolset.call_tool):
                        ctx = RunContext(deps=None, model=TestModel(), usage=RunUsage())

                        async def _call():
                            tools = await toolset.get_tools(ctx)
                            tool = tools.get(tool_name)
                            if tool is None:
                                return None
                            return await toolset.call_tool(tool_name, tool_args, ctx, tool)

                        result = _run_coroutine_sync(_call())
                        if result is None:
                            continue
                    else:
                        ctx = RunContext(deps=None, model=TestModel(), usage=RunUsage())
                        tools = _run_coroutine_sync(toolset.get_tools(ctx))
                        tool = tools.get(tool_name)
                        if tool is None:
                            continue
                        logger.debug("[TOOL_EXEC] Toolset call_tool is sync, calling directly")
                        result = toolset.call_tool(tool_name, tool_args, ctx, tool)

                    logger.debug(f"[TOOL_EXEC] MCP tool '{tool_name}' returned: {result}")
                    return result
                except Exception as e:
                    logger.error(
                        f"[TOOL_EXEC] MCP tool '{tool_name}' execution failed: {e}",
                        exc_info=True,
                    )
                    return {"error": str(e)}

        logger.warning(f"[TOOL_EXEC] Tool '{tool_name}' not found in any toolset")
        return {"error": f"Tool '{tool_name}' not found"}

    def _build_module(self) -> TactusModule:
        """Build the internal DSPy module for this agent."""
        # Create a signature for agent turns
        # Input: system_prompt, history, user_message
        # If tools available: also include tools as structured list[dspy.Tool]
        # Output: response and tool_calls (if tools are needed)

        # Use DSPy's native function calling with structured tool input
        # See: dspy/adapters/base.py - adapter preprocesses tools field
        if self.tools or self.toolsets:
            signature = "system_prompt, history, user_message, tools: list[dspy.Tool] -> response, tool_calls: dspy.ToolCalls"
        else:
            signature = "system_prompt, history, user_message -> response"

        return create_module(
            f"{self.name}_module",
            {
                "signature": signature,
                "strategy": self._module_to_strategy(self.module),
            },
        )

    def _should_stream(self) -> bool:
        """
        Determine if streaming should be enabled for this agent.

        Streaming is enabled when:
        - log_handler is available (for emitting events)
        - log_handler supports streaming events
        - disable_streaming is False
        - No structured output schema (streaming only works with plain text)

        Returns:
            True if streaming should be enabled
        """
        # CRITICAL DEBUG: Always log entry
        # logger.info(f"[STREAMING] Agent '{self.name}': _should_stream() called")

        # Must have log_handler to emit streaming events
        if self.log_handler is None:
            # logger.info(
            #     f"[STREAMING] Agent '{self.name}': no log_handler, streaming disabled"
            # )
            return False

        # Allow log handlers to opt out of streaming (e.g., cost-only collectors)
        supports_streaming = getattr(self.log_handler, "supports_streaming", True)
        # logger.info(
        #     f"[STREAMING] Agent '{self.name}': "
        #     f"log_handler.supports_streaming={supports_streaming}"
        # )
        if not supports_streaming:
            # logger.info(
            #     f"[STREAMING] Agent '{self.name}': "
            #     "log_handler supports_streaming=False, streaming disabled"
            # )
            return False

        # Respect explicit disable flag
        # logger.info(
        #     f"[STREAMING] Agent '{self.name}': disable_streaming={self.disable_streaming}"
        # )
        if self.disable_streaming:
            # logger.info(
            #     f"[STREAMING] Agent '{self.name}': "
            #     "disable_streaming=True, streaming disabled"
            # )
            return False

        # Note: We intentionally allow streaming even with output_schema.
        # Streaming (UI feedback) and validation (post-processing) are orthogonal.
        # Stream raw text to UI during generation, then validate after completion.

        # logger.info(f"[STREAMING] Agent '{self.name}': streaming ENABLED")
        return True

    def _emit_cost_event(self) -> None:
        """
        Emit a CostEvent based on the most recent LLM call in the LM history.

        Extracts usage and cost information from DSPy's LM history and emits
        a CostEvent for tracking in the IDE.
        """
        if self.log_handler is None:
            return

        from tactus.protocols.models import CostEvent

        # Get the current LM
        lm = dspy.settings.lm
        if lm is None or not hasattr(lm, "history") or not lm.history:
            logger.debug(f"[COST] Agent '{self.name}': no LM history available")
            return

        # Get the most recent call
        last_call = lm.history[-1]

        # Extract usage information
        usage = last_call.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", 0)

        # Extract cost information
        total_cost = last_call.get("cost")
        logger.debug(f"[COST] Agent '{self.name}': raw cost from history = {total_cost}")

        # If cost is None (happens with streamify()), calculate it using LiteLLM
        if total_cost is None:
            response = last_call.get("response")
            if response and hasattr(response, "_hidden_params"):
                total_cost = response._hidden_params.get("response_cost")
                logger.debug(f"[COST] Agent '{self.name}': cost from _hidden_params = {total_cost}")

            # If still None, calculate manually using litellm.completion_cost
            if total_cost is None and response:
                try:
                    import litellm

                    total_cost = litellm.completion_cost(completion_response=response)
                    logger.debug(f"[COST] Agent '{self.name}': calculated cost = {total_cost}")
                except Exception as e:
                    logger.warning(f"[COST] Agent '{self.name}': failed to calculate cost: {e}")
                    total_cost = 0.0
            elif total_cost is None:
                total_cost = 0.0
                logger.warning(f"[COST] Agent '{self.name}': no cost information available")

        # Calculate per-token costs (approximate)
        # Note: LiteLLM provides total cost, we can approximate prompt/completion split
        # based on token ratios
        if total_tokens > 0 and total_cost > 0:
            prompt_cost = total_cost * (prompt_tokens / total_tokens)
            completion_cost = total_cost * (completion_tokens / total_tokens)
        else:
            prompt_cost = 0.0
            completion_cost = 0.0

        # Extract duration from response metadata
        response = last_call.get("response")
        duration_ms = None
        if response and hasattr(response, "_hidden_params"):
            duration_ms = response._hidden_params.get("_response_ms")

        # Extract model info
        model = last_call.get("model", self.model or "unknown")

        # Parse provider from model string (e.g., "openai/gpt-4o" -> "openai")
        provider = "unknown"
        if "/" in str(model):
            provider = str(model).split("/")[0]

        # Create and emit cost event
        cost_event = CostEvent(
            agent_name=self.name,
            model=model,
            provider=provider,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            prompt_cost=prompt_cost,
            completion_cost=completion_cost,
            total_cost=total_cost,
            duration_ms=duration_ms,
        )

        self.log_handler.log(cost_event)
        logger.debug(
            "[COST] Agent '%s': $%.6f (%s tokens)",
            self.name,
            total_cost,
            total_tokens,
        )

    def _log_llm_debug_input(self, prompt_context: Dict[str, Any]) -> None:
        """Log the full conversation context being sent to the LLM."""
        logger.info("=" * 80)
        logger.info(f"[LLM_DEBUG] Agent '{self.name}' — Turn {self._turn_count}")
        logger.info("=" * 80)
        logger.info("[LLM_DEBUG] SYSTEM PROMPT:")
        logger.info(prompt_context.get("system_prompt", "(none)"))
        logger.info("-" * 40)
        logger.info("[LLM_DEBUG] HISTORY:")
        history = prompt_context.get("history", [])
        if hasattr(history, "messages"):
            history = history.messages
        for i, msg in enumerate(history if isinstance(history, list) else []):
            role = msg.get("role", "?") if isinstance(msg, dict) else "?"
            content = str(msg.get("content", "")) if isinstance(msg, dict) else str(msg)
            truncated = content[:500] + "..." if len(content) > 500 else content
            logger.info(f"  [{i}] {role}: {truncated}")
        logger.info("-" * 40)
        logger.info("[LLM_DEBUG] USER MESSAGE:")
        logger.info(prompt_context.get("user_message", "(none)"))
        if "tools" in prompt_context:
            tools = prompt_context["tools"]
            logger.info(f"[LLM_DEBUG] TOOLS: {len(tools)} available")
            for t in tools:
                name = getattr(t, "name", None) or getattr(t, "__name__", str(t))
                logger.info(f"  - {name}")
        logger.info("=" * 80)

    def _log_llm_debug_output(self, dspy_result: Any) -> None:
        """Log the full LLM output."""
        logger.info("[LLM_DEBUG] MODEL RESPONSE:")
        if hasattr(dspy_result, "response"):
            logger.info(dspy_result.response)
        if hasattr(dspy_result, "tool_calls") and dspy_result.tool_calls:
            logger.info(f"[LLM_DEBUG] TOOL CALLS: {dspy_result.tool_calls}")
        logger.info("=" * 80)

    def _turn_with_streaming(
        self,
        opts: Dict[str, Any],
        prompt_context: Dict[str, Any],
    ) -> TactusResult:
        """
        Execute an agent turn with streaming enabled.

        Uses DSPy's streamify() to wrap the module for streaming output.
        Runs in a separate thread to avoid event loop conflicts.
        Chunks are emitted as AgentStreamChunkEvent for real-time display in the UI.

        Args:
            opts: Turn options
            prompt_context: Prepared prompt context for the module

        Returns:
            TactusResult with value, usage, and cost_stats
        """
        from tactus.protocols.models import AgentTurnEvent, AgentStreamChunkEvent

        # logger.info(f"[STREAMING] Agent '{self.name}' starting streaming turn")

        # Debug: log full LLM input
        if os.environ.get("PLEXUS_DEBUG_LLM"):
            self._log_llm_debug_input(prompt_context)

        # Emit turn started event so the UI shows a loading indicator
        self.log_handler.log(
            AgentTurnEvent(
                agent_name=self.name,
                stage="started",
            )
        )
        # logger.info(f"[STREAMING] Agent '{self.name}' emitted AgentTurnEvent(started)")

        # Queue for passing chunks from streaming thread to main thread
        chunk_queue = queue.Queue()
        result_holder = {"result": None, "error": None}

        def run_streaming_in_thread():
            """Run DSPy streaming in a separate thread with its own event loop."""
            dspy_thread = dspy

            async def async_streaming():
                """Async function that runs the streaming module."""
                try:
                    # Create a streaming version of the module using DSPy's streamify
                    # NOTE: streamify() automatically enables streaming on the LM
                    # We do NOT need to use settings.context(stream=True) - that actually breaks it!
                    streaming_module = dspy_thread.streamify(self._module.module)
                    # logger.info(
                    #     f"[STREAMING] Agent '{self.name}' created streaming module"
                    # )

                    # Call the streaming module - it returns an async generator
                    stream = streaming_module(**prompt_context)

                    chunk_count = 0
                    async for value in stream:
                        chunk_count += 1
                        # Check for final Prediction first
                        if isinstance(value, dspy_thread.Prediction):
                            # Final prediction - this is the result
                            # logger.info(
                            #     f"[STREAMING] Agent '{self.name}' received final Prediction"
                            # )
                            result_holder["result"] = value
                        # Check for ModelResponseStream (the actual streaming chunks!)
                        elif hasattr(value, "choices") and value.choices:
                            delta = value.choices[0].delta
                            if hasattr(delta, "content") and delta.content:
                                # logger.info(
                                #     f"[STREAMING] Agent '{self.name}' "
                                #     f"chunk #{chunk_count}: '{delta.content}'"
                                # )
                                chunk_queue.put(("chunk", delta.content))
                        # String chunks (shouldn't happen with DSPy but handle it anyway)
                        elif isinstance(value, str):
                            # logger.info(
                            #     f"[STREAMING] Agent '{self.name}' "
                            #     f"got STRING chunk, len={len(value)}"
                            # )
                            if value:
                                chunk_queue.put(("chunk", value))
                        else:
                            pass

                    # logger.info(
                    #     f"[STREAMING] Agent '{self.name}' "
                    #     f"stream finished, processed {chunk_count} values"
                    # )

                except Exception as e:
                    # logger.error(
                    #     f"[STREAMING] Agent '{self.name}' error: {e}",
                    #     exc_info=True,
                    # )
                    result_holder["error"] = e
                finally:
                    # Signal end of stream
                    chunk_queue.put(("done", None))

            # Run the async function in this thread's new event loop
            asyncio.run(async_streaming())

        # Start streaming in a separate thread
        streaming_thread = threading.Thread(target=run_streaming_in_thread, daemon=True)
        streaming_thread.start()

        # Consume chunks from the queue and emit events in the main thread
        accumulated_text = ""
        emitted_count = 0
        # logger.info(f"[STREAMING] Agent '{self.name}' consuming chunks from queue")

        while True:
            try:
                msg_type, msg_data = chunk_queue.get(timeout=120.0)  # 2 minute timeout
                if msg_type == "done":
                    break
                elif msg_type == "chunk" and msg_data:
                    accumulated_text += msg_data
                    emitted_count += 1
                    event = AgentStreamChunkEvent(
                        agent_name=self.name,
                        chunk_text=msg_data,
                        accumulated_text=accumulated_text,
                    )
                    # logger.info(
                    #     f"[STREAMING] Agent '{self.name}' emitting chunk "
                    #     f"{emitted_count}, len={len(msg_data)}"
                    # )
                    self.log_handler.log(event)
            except queue.Empty:
                # logger.warning(
                #     f"[STREAMING] Agent '{self.name}' timeout waiting for chunks"
                # )
                break

        # Wait for thread to complete
        streaming_thread.join(timeout=5.0)

        # logger.info(
        #     f"[STREAMING] Agent '{self.name}' finished, emitted {emitted_count} events"
        # )

        # Check for errors
        if result_holder["error"] is not None:
            error = result_holder["error"]

            # Unwrap ExceptionGroup to find the real error
            original_error = error
            if hasattr(error, "__class__") and error.__class__.__name__ == "ExceptionGroup":
                # Python 3.11+ ExceptionGroup
                if hasattr(error, "exceptions") and error.exceptions:
                    original_error = error.exceptions[0]

            # Check if it's an authentication error (in original or wrapped)
            error_str = str(original_error).lower()
            error_type = str(type(original_error).__name__)

            if "authenticationerror" in error_type.lower() or "api_key" in error_str:
                from tactus.core.exceptions import TactusRuntimeError

                raise TactusRuntimeError(
                    f"API authentication failed for agent '{self.name}': "
                    f"Missing or invalid API key. Please configure your API key in Settings (Cmd+,)."
                ) from error

            # Unwrap ExceptionGroup so the real error is visible in logs/pcall
            if original_error is not error:
                logger.error(
                    f"Agent '{self.name}' ExceptionGroup sub-exception: "
                    f"{type(original_error).__name__}: {original_error}"
                )
                raise RuntimeError(
                    f"Agent '{self.name}' failed: {type(original_error).__name__}: {original_error}"
                ) from original_error
            raise result_holder["error"]

        # If streaming failed to produce a result, fall back to non-streaming
        if result_holder["result"] is None:
            logger.warning(f"Streaming produced no result for agent '{self.name}', falling back")
            return self._turn_without_streaming(opts, prompt_context)

        # Debug: log full LLM output after streaming completes
        if os.environ.get("PLEXUS_DEBUG_LLM"):
            self._log_llm_debug_output(result_holder["result"])

        # Track new messages for this turn
        new_messages = []

        # Determine user message
        user_message = opts.get("message")
        if self._turn_count == 1 and not user_message and self.initial_message:
            user_message = self.initial_message

        # Add user message to new_messages if present
        if user_message:
            user_msg = {"role": "user", "content": user_message}
            new_messages.append(user_msg)
            self._history.add(user_msg)

        # Add assistant response to new_messages
        if hasattr(result_holder["result"], "response"):
            assistant_msg = {"role": "assistant", "content": result_holder["result"].response}

            # Include tool calls in the message if present (before wrapping)
            if (
                hasattr(result_holder["result"], "tool_calls")
                and result_holder["result"].tool_calls
            ):
                # Convert tool calls to JSON-serializable format
                # logger.info("[ASYNC_STREAMING] Converting tool_calls to dict format")
                tool_calls_list = []
                for tc in (
                    result_holder["result"].tool_calls.tool_calls
                    if hasattr(result_holder["result"].tool_calls, "tool_calls")
                    else []
                ):
                    tc_name, tc_args = _tool_call_name_and_args(tc)
                    tool_calls_list.append(
                        {
                            "id": _tool_call_id_for_history(tc),
                            "type": "function",
                            "function": {
                                "name": tc_name,
                                "arguments": (
                                    json.dumps(tc_args) if isinstance(tc_args, dict) else tc_args
                                ),
                            },
                        }
                    )
                # logger.info(
                #     f"[ASYNC_STREAMING] Built tool_calls_list with "
                #     f"{len(tool_calls_list)} items"
                # )
                if tool_calls_list:
                    assistant_msg["tool_calls"] = tool_calls_list
                    # logger.info("[ASYNC_STREAMING] Added tool_calls to assistant_msg")

            new_messages.append(assistant_msg)
            self._history.add(assistant_msg)

            # Execute tool calls and add tool result messages to history
            if assistant_msg.get("tool_calls"):
                # logger.info(
                #     f"[ASYNC_STREAMING] Agent '{self.name}' executing "
                #     f"{len(assistant_msg['tool_calls'])} tool calls"
                # )
                for tc in assistant_msg["tool_calls"]:
                    tool_name = tc["function"]["name"]
                    tool_args_str = tc["function"]["arguments"]
                    tool_args = (
                        json.loads(tool_args_str)
                        if isinstance(tool_args_str, str)
                        else tool_args_str
                    )
                    tool_id = tc["id"]

                    # logger.info(
                    #     f"[ASYNC_STREAMING] Executing tool: {tool_name} "
                    #     f"with args: {tool_args}"
                    # )

                    # Execute the tool using toolsets
                    tool_result = self._execute_tool(tool_name, tool_args)
                    # logger.info(
                    #     f"[ASYNC_STREAMING] Tool executed successfully: {tool_result}"
                    # )

                    # Record the tool call so Lua can check if it was called
                    tool_primitive = getattr(self, "_tool_primitive", None)
                    if tool_primitive:
                        # Remove agent name prefix from tool name if present
                        # Tool names are stored as "agent_name_tool_name" in the primitive
                        clean_tool_name = tool_name.replace(f"{self.name}_", "")
                        tool_primitive.record_call(
                            clean_tool_name, tool_args, tool_result, agent_name=self.name
                        )
                        # logger.info(
                        #     f"[ASYNC_STREAMING] Recorded tool call: {clean_tool_name}"
                        # )

                    # Add tool result to history in OpenAI's expected format
                    # OpenAI requires: role="tool", tool_call_id=<id>, content=<result>
                    tool_result_str = (
                        json.dumps(tool_result)
                        if isinstance(tool_result, dict)
                        else str(tool_result)
                    )
                    tool_result_msg = {
                        "role": "tool",
                        "tool_call_id": tool_id,
                        "name": tool_name,
                        "content": tool_result_str,
                    }
                    # logger.info(
                    #     f"[ASYNC_STREAMING] Created tool result message: {tool_result_msg}"
                    # )
                    new_messages.append(tool_result_msg)
                    # logger.info(
                    #     f"[ASYNC_STREAMING] Added tool result to new_messages, "
                    #     f"count={len(new_messages)}"
                    # )
                    self._history.add(tool_result_msg)
                    # logger.info(
                    #     f"[ASYNC_STREAMING] Added tool result to history for "
                    #     f"tool_call_id={tool_id}, history size={len(self._history)}"
                    # )

        # Wrap the result with message tracking
        wrapped_result = wrap_prediction(
            result_holder["result"],
            new_messages=new_messages,
            all_messages=self._history.get(),
        )

        # Handle tool calls if present — only record done if not already captured by [TOOL_EXEC]
        if hasattr(wrapped_result, "tool_calls") and wrapped_result.tool_calls:
            tool_primitive = getattr(self, "_tool_primitive", None)
            if tool_primitive and "done" in str(wrapped_result.tool_calls).lower():
                existing = (
                    tool_primitive.last_call("done")
                    if hasattr(tool_primitive, "last_call")
                    else None
                )
                if existing is None:
                    reason = (
                        wrapped_result.response
                        if hasattr(wrapped_result, "response")
                        else "Task completed"
                    )
                    logger.debug(f"Recording done tool call with reason: {reason}")
                    tool_primitive.record_call(
                        "done",
                        {"reason": reason},
                        {"status": "completed", "reason": reason, "tool": "done"},
                        agent_name=self.name,
                    )

        # Emit turn completed event
        self.log_handler.log(
            AgentTurnEvent(
                agent_name=self.name,
                stage="completed",
            )
        )
        # logger.info(
        #     f"[STREAMING] Agent '{self.name}' emitted AgentTurnEvent(completed)"
        # )

        # Extract usage and cost stats
        usage_stats, cost_stats = self._extract_last_call_stats()

        # Emit cost event with usage and cost information
        self._emit_cost_event()

        # Wrap as TactusResult with value, usage, and cost
        return self._wrap_as_result(wrapped_result, usage_stats, cost_stats)

    def _turn_without_streaming(
        self,
        opts: Dict[str, Any],
        prompt_context: Dict[str, Any],
    ) -> TactusResult:
        """
        Execute an agent turn without streaming.

        This is the standard execution path that waits for the full response.

        Args:
            opts: Turn options
            prompt_context: Prepared prompt context for the module

        Returns:
            TactusResult with value, usage, and cost_stats
        """
        # Debug: log full LLM input
        if os.environ.get("PLEXUS_DEBUG_LLM"):
            self._log_llm_debug_input(prompt_context)

        # Execute the module
        dspy_result = self._module.module(**prompt_context)

        # Debug: log full LLM output
        if os.environ.get("PLEXUS_DEBUG_LLM"):
            self._log_llm_debug_output(dspy_result)

        # Track new messages for this turn
        new_messages = []

        # Determine user message
        user_message = opts.get("message")
        if self._turn_count == 1 and not user_message and self.initial_message:
            user_message = self.initial_message

        # Add user message to new_messages if present
        if user_message:
            user_msg = {"role": "user", "content": user_message}
            new_messages.append(user_msg)
            self._history.add(user_msg)

        # Add assistant response to new_messages
        if hasattr(dspy_result, "response"):
            assistant_msg = {"role": "assistant", "content": dspy_result.response}

            # Include tool calls in the message if present (before wrapping)
            has_tc = hasattr(dspy_result, "tool_calls")
            tc_value = getattr(dspy_result, "tool_calls", None)
            logger.debug(
                f"Agent '{self.name}' dspy_result: has_tool_calls={has_tc}, tool_calls={tc_value}"
            )
            if hasattr(dspy_result, "tool_calls") and dspy_result.tool_calls:
                # Convert tool calls to JSON-serializable format
                tool_calls_list = []
                for tc in (
                    dspy_result.tool_calls.tool_calls
                    if hasattr(dspy_result.tool_calls, "tool_calls")
                    else []
                ):
                    tc_name, tc_args = _tool_call_name_and_args(tc)
                    tool_calls_list.append(
                        {
                            "id": _tool_call_id_for_history(tc),
                            "type": "function",
                            "function": {
                                "name": tc_name,
                                "arguments": (
                                    json.dumps(tc_args) if isinstance(tc_args, dict) else tc_args
                                ),
                            },
                        }
                    )
                if tool_calls_list:
                    assistant_msg["tool_calls"] = tool_calls_list

            new_messages.append(assistant_msg)
            self._history.add(assistant_msg)

            # Execute tool calls and add tool result messages (OpenAI requires tool
            # messages for every tool_call_id before the next user turn). Mirrors
            # _turn_with_streaming_async.
            if assistant_msg.get("tool_calls"):
                for tc in assistant_msg["tool_calls"]:
                    tool_name = tc["function"]["name"]
                    tool_args_str = tc["function"]["arguments"]
                    tool_args = (
                        json.loads(tool_args_str)
                        if isinstance(tool_args_str, str)
                        else tool_args_str
                    )
                    tool_id = tc["id"]
                    clean_tool_name = tool_name.replace(f"{self.name}_", "")
                    tool_primitive = getattr(self, "_tool_primitive", None)
                    tool_result = None
                    if tool_primitive:
                        prior = (
                            tool_primitive.last_call(clean_tool_name)
                            if hasattr(tool_primitive, "last_call")
                            else None
                        )
                        if prior is not None:
                            tool_result = prior.get("result")
                    if tool_result is None:
                        tool_result = self._execute_tool(tool_name, tool_args)
                    # Else: forward path already ran the tool and recorded it; only sync history.
                    tool_result_str = (
                        json.dumps(tool_result)
                        if isinstance(tool_result, dict)
                        else str(tool_result)
                    )
                    tool_result_msg = {
                        "role": "tool",
                        "tool_call_id": tool_id,
                        "name": tool_name,
                        "content": tool_result_str,
                    }
                    new_messages.append(tool_result_msg)
                    self._history.add(tool_result_msg)

        # Wrap the result with message tracking
        wrapped_result = wrap_prediction(
            dspy_result,
            new_messages=new_messages,
            all_messages=self._history.get(),
        )

        # Handle tool calls if present — only record done if not already captured by [TOOL_EXEC]
        if hasattr(wrapped_result, "tool_calls") and wrapped_result.tool_calls:
            tool_primitive = getattr(self, "_tool_primitive", None)
            if tool_primitive and "done" in str(wrapped_result.tool_calls).lower():
                existing = (
                    tool_primitive.last_call("done")
                    if hasattr(tool_primitive, "last_call")
                    else None
                )
                if existing is None:
                    reason = (
                        wrapped_result.response
                        if hasattr(wrapped_result, "response")
                        else "Task completed"
                    )
                    logger.debug(f"Recording done tool call with reason: {reason}")
                    tool_primitive.record_call(
                        "done",
                        {"reason": reason},
                        {"status": "completed", "reason": reason, "tool": "done"},
                        agent_name=self.name,
                    )

        # Extract usage and cost stats
        usage_stats, cost_stats = self._extract_last_call_stats()

        # Emit cost event with usage and cost information
        self._emit_cost_event()

        # Wrap as TactusResult with value, usage, and cost
        return self._wrap_as_result(wrapped_result, usage_stats, cost_stats)

    def __call__(self, inputs: Optional[Dict[str, Any]] = None) -> Any:
        """
        Execute an agent turn using the callable interface.

        This is the unified callable interface that allows:
            result = worker({message = "Hello"})

        Args:
            inputs: Input dict with fields matching input_schema.
                   Default field 'message' is used as the user message.
                   Additional fields are passed as context.
                   Can also include per-turn overrides like:
                   - tools: List[Any] - Tool/toolset references and toolset expressions to use
                   - temperature: float - Override temperature
                   - max_tokens: int - Override max_tokens
                   - system_prompt: str - Replace the agent's template for this turn (still resolves {state.*}, {params.*}, etc.)
                   - system_prompt_suffix: str - Append after the rendered default agent system prompt (mutually exclusive with system_prompt override for this turn)

        Returns:
            Result object with response and other fields

        Example (Lua):
            result = worker({message = "Process this task"})
            print(result.response)
        """
        logger.debug(f"Agent '{self.name}' invoked via __call__()")
        # Convenience: allow shorthand string calls in Lua:
        #   worker("Hello") == worker({message = "Hello"})
        if isinstance(inputs, str):
            inputs = {"message": inputs}

        inputs = inputs or {}

        # Convert Lua table to dict if needed
        if hasattr(inputs, "items"):
            try:
                inputs = dict(inputs.items())
            except (AttributeError, TypeError) as exc:
                logger.debug("Agent '%s' could not coerce inputs mapping: %s", self.name, exc)

        # Extract message field (the main input)
        message = inputs.get("message")

        # Build turn options (keeping per-turn overrides like tools, temperature, etc.)
        opts = {}
        if message:
            opts["message"] = message

        # Pass remaining fields - some are per-turn overrides, others are context
        override_keys = {
            "tools",
            "temperature",
            "max_tokens",
            "system_prompt",
            "system_prompt_suffix",
        }
        for key in override_keys:
            if key in inputs:
                opts[key] = inputs[key]

        # Everything else goes into context
        context = {k: v for k, v in inputs.items() if k not in ({"message"} | override_keys)}
        if context:
            opts["context"] = context

        # If execution_context is available, wrap in checkpoint for transparent durability
        if self.execution_context:

            def checkpoint_fn():
                return self._execute_turn(opts)

            result = self.execution_context.checkpoint(checkpoint_fn, f"agent_{self.name}_turn")
        else:
            # No checkpointing - execute directly
            result = self._execute_turn(opts)

        # Mirror AgentHandle convenience for Lua patterns like `agent(); return agent.output`.
        output_text = None
        if result is not None:
            for attr in ("response", "message"):
                try:
                    value = getattr(result, attr, None)
                except Exception:
                    value = None
                if isinstance(value, str):
                    output_text = value
                    break

            if output_text is None and isinstance(result, dict):
                for key in ("response", "message"):
                    value = result.get(key)
                    if isinstance(value, str):
                        output_text = value
                        break

            if output_text is None:
                if hasattr(result, "output") and isinstance(result.output, str):
                    output_text = result.output
                else:
                    output_text = str(result)

        self.output = output_text
        return result

    def _execute_turn(self, opts: Dict[str, Any]) -> Any:
        """
        Execute a single agent turn (internal method for checkpointing).

        This method contains the core agent execution logic that gets checkpointed.

        Args:
            opts: Turn options with message, context, and per-turn overrides

        Returns:
            Result object with response and other fields
        """
        # Execute the turn (inlined from old turn() method)
        self._turn_count += 1
        logger.debug(f"Agent '{self.name}' turn {self._turn_count}")

        # Check for mock first (before any LLM calls)
        if self.mock_manager and self.registry:
            mock_response = self._get_mock_response(opts)
            if mock_response is not None:
                logger.debug(f"Agent '{self.name}' returning mock response")
                return mock_response

        # Auto-configure LM if not already configured
        from tactus.dspy.config import get_current_lm, configure_lm

        if get_current_lm() is None and self.model:
            model_for_litellm = _normalize_model_for_litellm(self.model, self.provider)
            logger.debug(f"Auto-configuring DSPy LM with model: {model_for_litellm}")

            # Build kwargs for configure_lm — omit temperature when None so configure_lm
            # applies defaults (0.0 for most models; omit for GPT-5 family).
            config_kwargs = {}
            if self.temperature is not None:
                config_kwargs["temperature"] = self.temperature
            if self.max_tokens is not None:
                config_kwargs["max_tokens"] = self.max_tokens
            if self.model_type is not None:
                config_kwargs["model_type"] = self.model_type
            if self.tool_choice is not None and (self.tools or self.toolsets):
                config_kwargs["tool_choice"] = self.tool_choice
                logger.debug(f"Configuring LM with tool_choice={self.tool_choice}")

            configure_lm(model_for_litellm, **config_kwargs)

        # Extract options
        user_message = opts.get("message")

        # Use initial_message on first turn if no inject provided
        if self._turn_count == 1 and not user_message and self.initial_message:
            user_message = self.initial_message

        context = opts.get("context") or {}

        prepared = self._run_prepare_hook(context, user_message)
        template = self.system_prompt
        suffix_template = None
        if "system_prompt" in opts and opts["system_prompt"] is not None:
            template = opts["system_prompt"]
        elif "system_prompt_suffix" in opts and opts.get("system_prompt_suffix") is not None:
            suffix_template = opts["system_prompt_suffix"]
        system_prompt = self._render_system_prompt(
            template, context=context, prepared=prepared, user_message=user_message
        )
        if suffix_template is not None:
            suffix_rendered = self._render_system_prompt(
                suffix_template,
                context=context,
                prepared=prepared,
                user_message=user_message,
            )
            system_prompt = f"{system_prompt}\n\n{suffix_rendered}"

        if self.context_name:
            if not self.registry or not hasattr(self.registry, "contexts"):
                raise RuntimeError("Context assembly requires a registry with contexts")

            from tactus.core.context_assembler import ContextAssembler
            from tactus.dspy.history import TactusHistory

            template_context = {
                "input": context,
                "context": getattr(self, "_context", {}) or {},
            }
            template_context.setdefault("input", {})
            if user_message:
                template_context["input"].setdefault("message", user_message)
                template_context["input"].setdefault("question", user_message)
            assembler = ContextAssembler(
                self.registry.contexts,
                retriever_registry=getattr(self.registry, "retrievers", None),
                corpus_registry=getattr(self.registry, "corpora", None),
                compactor_registry=getattr(self.registry, "compactors", None),
            )
            assembly = assembler.assemble(
                context_name=self.context_name,
                base_system_prompt=system_prompt,
                history_messages=self._filter_history(self._history.get(), context, prepared),
                user_message=user_message or "",
                template_context=template_context,
            )

            prompt_context = {
                "system_prompt": assembly.system_prompt,
                "history": TactusHistory(messages=assembly.history).to_dspy(),
                "user_message": assembly.user_message,
            }
        else:
            # Build the prompt context
            prompt_context = {
                "system_prompt": system_prompt,
                "history": self._history_from_messages(
                    self._filter_history(self._history.get(), context, prepared)
                ),
                "user_message": user_message or "",
            }

        # Add tools as structured DSPy Tool objects if agent has them
        # DSPy's adapter will convert these to OpenAI function call format
        if self.tools or self.toolsets:
            dspy_tools = self._convert_toolsets_to_dspy_tools_sync()
            prompt_context["tools"] = dspy_tools
            logger.debug(f"Agent '{self.name}' passing {len(dspy_tools)} DSPy tools to module")

        # Add any injected context (user_message is already in prompt_context)
        if context:
            prompt_context["context"] = context

        return self._turn_with_retries(opts, prompt_context)

    def _run_prepare_hook(
        self, context: Dict[str, Any], user_message: Optional[str]
    ) -> dict[str, Any]:
        if not callable(self.prepare):
            return {}
        try:
            prepared = self.prepare()
        except TypeError:
            try:
                prepared = self.prepare({"context": context, "message": user_message})
            except Exception as error:
                logger.warning(
                    "Agent '%s' prepare hook failed: %s", self.name, error, exc_info=True
                )
                return {}
        except Exception as error:
            logger.warning("Agent '%s' prepare hook failed: %s", self.name, error, exc_info=True)
            return {}

        if prepared is None:
            return {}
        if hasattr(prepared, "items"):
            try:
                prepared = dict(prepared.items())
            except Exception as exc:
                logger.debug(
                    "Agent '%s' prepare output mapping coercion failed: %s", self.name, exc
                )
        if not isinstance(prepared, dict):
            return {"value": prepared}
        return prepared

    def _render_system_prompt(
        self,
        template: str,
        context: Dict[str, Any],
        prepared: Dict[str, Any],
        user_message: Optional[str],
    ) -> str:
        if not template:
            return template

        input_context = dict(context or {})
        if user_message and "message" not in input_context:
            input_context["message"] = user_message

        resolver = TemplateResolver(
            params=input_context,
            state=self._state_primitive.all() if getattr(self, "_state_primitive", None) else {},
            context=getattr(self, "_context", {}) or {},
            prepared=prepared or {},
            env=dict(os.environ),
        )
        # TemplateResolver uses {params.*}; keep {input.*} working by aliasing input -> params.
        return resolver.resolve(template.replace("{input.", "{params."))

    def _filter_history(
        self, messages: List[Dict[str, Any]], context: Dict[str, Any], prepared: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        if not self.message_history_filter:
            return messages
        manager = MessageHistoryManager()
        filter_context = {"context": context, "prepared": prepared, "input": context}
        return manager._apply_filter(messages, self.message_history_filter, filter_context)

    @staticmethod
    def _history_from_messages(messages: List[Dict[str, Any]]):
        return TactusHistory(messages=messages).to_dspy()

    def _turn_with_retries(
        self,
        opts: Dict[str, Any],
        prompt_context: Dict[str, Any],
    ) -> TactusResult:
        attempts = max(self.response_retries, 0) + 1
        history_length = len(self._history)

        for attempt in range(attempts):
            try:
                if self._should_stream():
                    logger.debug(f"Agent '{self.name}' using streaming mode")
                    result = self._turn_with_streaming(opts, prompt_context)
                else:
                    logger.debug(f"Agent '{self.name}' using non-streaming mode")
                    result = self._turn_without_streaming(opts, prompt_context)

                self._validate_output(result)
                return result
            except Exception as error:
                if attempt >= attempts - 1:
                    logger.debug("Agent '%s' turn failed: %s", self.name, error, exc_info=True)
                    raise
                self._history.truncate(history_length)
                if self.response_retry_delay > 0:
                    time.sleep(self.response_retry_delay)

        raise RuntimeError("Unexpected retry loop exit")  # pragma: no cover

    def _validate_output(self, result: TactusResult) -> None:
        if not self._explicit_output_schema:
            return
        output_schema = self.output_schema
        if hasattr(output_schema, "fields"):
            schema_fields = output_schema.fields
        else:
            schema_fields = output_schema or {}

        if not isinstance(schema_fields, dict) or not schema_fields:
            return

        if not isinstance(result.output, dict):
            if self.toolsets:
                # Expected for tool-calling chat agents (e.g. reply-only); not worth a user-visible warning.
                logger.debug(
                    "Agent '%s' produced non-dict output while using toolsets; skipping output validation",
                    self.name,
                )
                return
            raise ValueError("Agent output is not structured as expected")

        missing = []
        for field_name, field_def in schema_fields.items():
            required = False
            if hasattr(field_def, "required"):
                required = bool(field_def.required)
            elif isinstance(field_def, dict):
                required = bool(field_def.get("required", False))
            if required and field_name not in result.output:
                missing.append(field_name)

        if missing:
            raise ValueError(f"Agent output missing required fields: {', '.join(missing)}")

    def _get_mock_response(self, opts: Dict[str, Any]) -> Optional[TactusPrediction]:
        """
        Check if this agent has a mock configured and return mock response.

        Agent mocks are stored in registry.agent_mocks (not registry.mocks which is for tools).
        Agent mock configs specify tool_calls, message, data, and usage.

        Args:
            opts: The turn options

        Returns:
            TactusPrediction if mocked, None otherwise
        """
        agent_name = self.name

        # Check if agent has a mock in the registry (agent_mocks, not mocks)
        if not self.registry or agent_name not in self.registry.agent_mocks:
            return None

        # Get agent mock config from registry.agent_mocks
        mock_config = self.registry.agent_mocks[agent_name]

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
                idx = self._turn_count - 1  # 1-indexed turns
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
            else:
                message = mock_config.message
                tool_calls = mock_config.tool_calls
                data = mock_config.data
        else:
            message = mock_config.message
            tool_calls = mock_config.tool_calls
            data = mock_config.data

        # Convert AgentMockConfig to format expected by _wrap_mock_response.
        # Important: we do NOT embed `data`/`usage` inside the prediction output by default.
        # The canonical agent payload is `result.output`:
        # - If the agent has an explicit output schema, we allow structured output via `data`.
        # - Otherwise, `result.output` is the plain response string.
        mock_data = {
            "response": message,
            "tool_calls": tool_calls,
        }

        if self.output_schema and data:
            mock_data["data"] = data

        try:
            return self._wrap_mock_response(mock_data, opts)
        except Exception:
            # If wrapping throws an error, let it propagate
            raise

    def _wrap_mock_response(self, mock_data: Dict[str, Any], opts: Dict[str, Any]) -> TactusResult:
        """
        Wrap mock data as a TactusResult.

        Also handles special mock behaviors like recording done tool calls.

        Args:
            mock_data: The mock response data. Can contain either 'message' or 'response'
                      field for the text response. If 'message' is present and 'response'
                      is not, it will be normalized to 'response' to match the agent's
                      output signature.
            opts: The turn options

        Returns:
            TactusResult with value, usage, and cost_stats (zeroed for mocks)
        """
        from tactus.dspy.prediction import create_prediction

        response_text = None
        if "response" in mock_data and isinstance(mock_data.get("response"), str):
            response_text = mock_data["response"]
        elif "message" in mock_data and isinstance(mock_data.get("message"), str):
            response_text = mock_data["message"]
        else:
            response_text = ""

        # Track new messages for this turn
        new_messages = []

        # Determine user message
        user_message = opts.get("message")
        if self._turn_count == 1 and not user_message and self.initial_message:
            user_message = self.initial_message

        # Add user message to new_messages if present
        if user_message:
            user_msg = {"role": "user", "content": user_message}
            new_messages.append(user_msg)
            self._history.add(user_msg)

        # Add assistant response to new_messages
        if response_text:
            assistant_msg = {"role": "assistant", "content": response_text}
            new_messages.append(assistant_msg)
            self._history.add(assistant_msg)

        prediction_fields: Dict[str, Any] = {}

        tool_calls_list = mock_data.get("tool_calls", [])
        if tool_calls_list:
            prediction_fields["tool_calls"] = tool_calls_list

        # If the agent has an explicit output schema, allow structured output via mock `data`.
        # Otherwise default to plain string output.
        data = mock_data.get("data")
        if self.output_schema and isinstance(data, dict) and data:
            prediction_fields.update(data)
        else:
            prediction_fields["response"] = response_text

        # Add message tracking to prediction
        prediction_fields["__new_messages__"] = new_messages
        prediction_fields["__all_messages__"] = self._history.get()

        # Create prediction from normalized mock data
        result = create_prediction(**prediction_fields)

        # Record all tool calls from the mock
        # This allows mocks to trigger Tool.called(...) behavior
        # Use getattr since _tool_primitive is set externally by runtime
        tool_primitive = getattr(self, "_tool_primitive", None)
        if tool_calls_list and tool_primitive:
            if isinstance(tool_calls_list, list):
                for tool_call in tool_calls_list:
                    if isinstance(tool_call, dict) and "tool" in tool_call:
                        tool_name = tool_call["tool"]
                        tool_args = tool_call.get("args", {})

                        # For done tool, extract reason for result
                        if tool_name == "done":
                            reason = tool_args.get(
                                "reason",
                                response_text or "Task completed (mocked)",
                            )
                            tool_result = {"status": "completed", "reason": reason, "tool": "done"}
                        else:
                            # For other tools, use a generic result
                            tool_result = {"tool": tool_name, "args": tool_args}

                        logger.debug(f"Mock recording {tool_name} tool call")
                        tool_primitive.record_call(
                            tool_name,
                            tool_args,
                            tool_result,
                            agent_name=self.name,
                        )

        # Return as TactusResult with zeroed usage/cost (mocks don't incur costs)
        return self._wrap_as_result(result, UsageStats(), CostStats())

    def clear_history(self) -> None:
        """Clear the conversation history."""
        self._history.clear()
        self._turn_count = 0

    def get_history(self) -> List[Dict[str, Any]]:
        """Get the conversation history."""
        return self._history.get()

    @property
    def history(self) -> TactusHistory:
        """Get the history object."""
        return self._history


def create_dspy_agent(
    name: str,
    config: Dict[str, Any],
    registry: Any = None,
    mock_manager: Any = None,
    execution_context: Any = None,
) -> DSPyAgentHandle:
    """
    Create a DSPy-based Agent from configuration.

    This is the main entry point for creating DSPy agents.

    Args:
        name: Agent name
        config: Configuration dict with:
            - system_prompt: System prompt
            - model: Model name (LiteLLM format)
            - tools: List of tools
            - toolsets: List of toolset names
            - module: DSPy module type (default: "Predict"). Options: "Predict", "ChainOfThought"
            - Other optional configuration
        registry: Optional Registry instance for accessing mocks
        mock_manager: Optional MockManager instance for checking mocks
        execution_context: Optional ExecutionContext for checkpointing agent calls

    Returns:
        A DSPyAgentHandle instance

    Raises:
        ValueError: If no LM is configured (either via config or globally)
    """
    # Check if LM is configured either in config or globally
    from tactus.dspy.config import get_current_lm

    if not config.get("model") and not get_current_lm():
        raise ValueError("LM not configured. Please configure an LM before creating an agent.")

    return DSPyAgentHandle(
        name=name,
        system_prompt=config.get("system_prompt", ""),
        model=config.get("model"),
        provider=config.get("provider"),
        context_name=config.get("context"),
        tools=config.get("tools", []),
        toolsets=config.get("toolsets", []),
        output_schema=config.get("output_schema") or config.get("output"),
        temperature=config.get("temperature"),
        max_tokens=config.get("max_tokens"),
        model_type=config.get("model_type"),
        module=config.get("module", "Raw"),
        initial_message=config.get("initial_message"),
        registry=registry,
        mock_manager=mock_manager,
        log_handler=config.get("log_handler"),
        disable_streaming=config.get("disable_streaming", False),
        execution_context=execution_context,
        **{
            k: v
            for k, v in config.items()
            if k
            not in [
                "system_prompt",
                "model",
                "provider",
                "context",
                "tools",
                "toolsets",
                "output_schema",
                "output",
                "temperature",
                "max_tokens",
                "model_type",
                "module",
                "initial_message",
                "log_handler",
                "disable_streaming",
            ]
        },
    )
