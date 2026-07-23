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
import random
import threading
import time
import uuid
from contextlib import nullcontext
from dataclasses import dataclass
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

DEFAULT_MAX_TOOL_FOLLOWUP_ROUNDS = 16


@dataclass(frozen=True)
class ToolExecutionOutcome:
    had_tool_calls: bool = False
    terminal_done_called: bool = False


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
        reasoning_effort: Optional[str] = None,
        verbosity: Optional[str] = None,
        request_timeout: Optional[float] = None,
        steering_enabled: bool = True,
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
            reasoning_effort: Optional GPT-5-family reasoning effort control
            verbosity: Optional GPT-5-family response verbosity control
            request_timeout: Provider request timeout in seconds for streaming and non-streaming calls
            steering_enabled: Whether to query the chat recorder for mid-run steering
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
        self.reasoning_effort = reasoning_effort
        self.verbosity = verbosity
        self.request_timeout = request_timeout
        self.steering_enabled = steering_enabled
        self.module = module
        self.initial_message = initial_message
        self.registry = registry
        self.mock_manager = mock_manager
        self.log_handler = log_handler
        self.disable_streaming = disable_streaming
        self.chat_recorder = kwargs.get("chat_recorder")
        self.tool_choice = kwargs.get("tool_choice")  # Extract tool_choice from kwargs
        self.prepare = kwargs.get("prepare")
        self._agent_lm = None
        self._agent_lm_key = None
        self._agent_adapter = None
        lifecycle_hooks = kwargs.get("lifecycle_hooks") or []
        if callable(lifecycle_hooks):
            lifecycle_hooks = [lifecycle_hooks]
        self.lifecycle_hooks = list(lifecycle_hooks)
        self._model_request_count = 0
        self.message_history_filter = kwargs.get("message_history_filter") or kwargs.get("filter")
        response_config = kwargs.get("response") or {}
        self.response_retries = int(response_config.get("retries", 0) or 0)
        self.response_retry_delay = float(response_config.get("retry_delay", 0.0) or 0.0)
        self.max_tool_followup_rounds = int(
            kwargs.get("max_tool_followup_rounds", DEFAULT_MAX_TOOL_FOLLOWUP_ROUNDS)
            or DEFAULT_MAX_TOOL_FOLLOWUP_ROUNDS
        )

        # First-class Agent retry configuration (preferred over response.retries).
        #
        # Backwards compatibility:
        # - If `retry` is absent, we keep the old behavior driven by response.retries.
        # - If `retry` is present, it overrides the legacy response-based settings.
        retry_config = kwargs.get("retry")
        if retry_config is None:
            retry_config = {}
        if hasattr(retry_config, "items"):
            try:
                retry_config = dict(retry_config.items())
            except Exception:
                retry_config = {}
        if not isinstance(retry_config, dict):
            retry_config = {}

        # `attempts` counts total attempts (including the first).
        attempts_raw = retry_config.get("attempts")
        if attempts_raw is None:
            # Allow legacy-ish spelling inside retry config.
            retries_raw = retry_config.get("retries")
            if retries_raw is not None:
                try:
                    attempts_raw = int(retries_raw) + 1
                except Exception:
                    attempts_raw = None

        enabled_raw = retry_config.get("enabled")
        if enabled_raw is None:
            # If attempts is explicitly set > 1, treat that as enabled.
            try:
                enabled_raw = int(attempts_raw or 0) > 1
            except Exception:
                enabled_raw = False

        self.retry_enabled = bool(enabled_raw)
        self.retry_attempts = max(1, int(attempts_raw or 1)) if self.retry_enabled else 1
        self.retry_delay_seconds = float(
            retry_config.get("delay_seconds", retry_config.get("delay", 0.0)) or 0.0
        )
        self.retry_max_delay_seconds = float(retry_config.get("max_delay_seconds", 0.0) or 0.0)
        self.retry_backoff = str(retry_config.get("backoff", "constant") or "constant").lower()
        self.retry_jitter = bool(retry_config.get("jitter", False))
        # What to retry:
        # - infra_only: retry runtime/transport-ish failures, not validation-style ValueErrors
        # - validation_only: retry validation-style ValueErrors, not infra
        # - infra_plus_validation: retry both (default when retry is enabled)
        self.retry_on = str(
            retry_config.get("on", "infra_plus_validation") or "infra_plus_validation"
        ).lower()

        # If retry is enabled, it supersedes legacy response retry settings.
        if self.retry_enabled:
            self.response_retries = 0
            self.response_retry_delay = 0.0

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

        # Last turn's text output (accessible from Lua as agent.output)
        self.output: Optional[str] = None

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

    @staticmethod
    def _to_tool_calls_list(dspy_result: Any) -> List[Dict[str, Any]]:
        """Convert DSPy tool_calls payload to history-compatible OpenAI tool call dicts."""
        if not hasattr(dspy_result, "tool_calls") or not dspy_result.tool_calls:
            return []

        tool_calls_list: List[Dict[str, Any]] = []
        raw_calls = (
            dspy_result.tool_calls.tool_calls
            if hasattr(dspy_result.tool_calls, "tool_calls")
            else []
        )
        for tc in raw_calls:
            tc_name, tc_args = _tool_call_name_and_args(tc)
            tool_calls_list.append(
                {
                    "id": _tool_call_id_for_history(tc),
                    "type": "function",
                    "function": {
                        "name": tc_name,
                        "arguments": json.dumps(tc_args) if isinstance(tc_args, dict) else tc_args,
                    },
                }
            )
        return tool_calls_list

    def _record_tool_execution(
        self, tool_name: str, tool_args: Dict[str, Any], tool_result: Any
    ) -> None:
        """Record tool execution in ToolPrimitive when available."""
        tool_primitive = getattr(self, "_tool_primitive", None)
        if not tool_primitive:
            return
        clean_tool_name = self._normalize_tool_name(tool_name)
        try:
            tool_primitive.record_call(
                clean_tool_name,
                tool_args,
                tool_result,
                agent_name=self.name,
            )
        except Exception:
            logger.debug("Failed to record tool execution for '%s'", clean_tool_name, exc_info=True)

    def _normalize_tool_name(self, tool_name: Any) -> str:
        name = str(tool_name or "")
        prefix = f"{self.name}_"
        if name.startswith(prefix):
            return name[len(prefix) :]
        return name

    def _is_terminal_done_tool(self, tool_name: Any) -> bool:
        return self._normalize_tool_name(tool_name) == "done"

    def _execute_assistant_tool_calls(
        self,
        assistant_msg: Dict[str, Any],
        new_messages: List[Dict[str, Any]],
    ) -> ToolExecutionOutcome:
        """Execute tool calls from an assistant message and append tool messages to history."""
        tool_calls = assistant_msg.get("tool_calls") or []
        if not tool_calls:
            return ToolExecutionOutcome()

        terminal_done_called = False
        for tc in tool_calls:
            tool_name = tc["function"]["name"]
            tool_args_str = tc["function"]["arguments"]
            tool_args = (
                json.loads(tool_args_str) if isinstance(tool_args_str, str) else tool_args_str
            )
            tool_id = tc["id"]

            tool_result = self._execute_tool(tool_name, tool_args)
            self._record_tool_execution(tool_name, tool_args, tool_result)
            terminal_done_called = terminal_done_called or self._is_terminal_done_tool(tool_name)

            tool_result_str = (
                json.dumps(tool_result) if isinstance(tool_result, dict) else str(tool_result)
            )
            tool_result_msg = {
                "role": "tool",
                "tool_call_id": tool_id,
                "name": tool_name,
                "content": tool_result_str,
            }
            new_messages.append(tool_result_msg)
            self._history.add(tool_result_msg)
            if terminal_done_called:
                break

        return ToolExecutionOutcome(
            had_tool_calls=True,
            terminal_done_called=terminal_done_called,
        )

    @staticmethod
    def _is_usable_assistant_text(text: Any) -> bool:
        return isinstance(text, str) and text.strip() != ""

    def _synthesis_prompt_context(self, prompt_context: Dict[str, Any]) -> Dict[str, Any]:
        """Build a one-shot finalization prompt context for no-text terminal turns."""
        synthesized = dict(prompt_context)
        synthesized["user_message"] = (
            "Provide the final user-facing answer now using prior tool results. "
            "Do not call tools."
        )
        return synthesized

    def _tool_followup_prompt_context(self, prompt_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build prompt context for the next model call after tool execution.

        Important: the original turn user_message must not be re-sent after tools run.
        Follow-up calls should rely on accumulated history (assistant tool call + tool results).
        """
        followup = dict(prompt_context)
        followup["history"] = self._history_from_messages(self._history.get())
        followup["user_message"] = ""
        return followup

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

        def _stream_once(current_prompt_context: Dict[str, Any]) -> Any:
            # Queue for passing chunks from streaming thread to main thread
            chunk_queue = queue.Queue()
            result_holder = {"result": None, "error": None}
            # Ensure lazy client/adapter initialization is complete before the
            # provider dispatch timestamp, even when this private helper is
            # exercised directly by a host or focused test.
            if self.model:
                self._get_agent_lm(opts)
            request_id = self._provider_request_started(current_prompt_context)
            first_chunk_emitted = False

            def run_streaming_in_thread():
                dspy_thread = dspy

                async def async_streaming():
                    try:
                        streaming_module = dspy_thread.streamify(self._module.module)
                        stream = streaming_module(**current_prompt_context)
                        async for value in stream:
                            if isinstance(value, dspy_thread.Prediction):
                                result_holder["result"] = value
                            elif hasattr(value, "choices") and value.choices:
                                delta = value.choices[0].delta
                                if hasattr(delta, "content") and delta.content:
                                    chunk_queue.put(("chunk", delta.content))
                            elif isinstance(value, str) and value:
                                chunk_queue.put(("chunk", value))
                    except Exception as e:
                        result_holder["error"] = e
                    finally:
                        chunk_queue.put(("done", None))

                with self._dspy_lm_context(opts):
                    asyncio.run(async_streaming())

            streaming_thread = threading.Thread(target=run_streaming_in_thread, daemon=True)
            streaming_thread.start()
            accumulated_text = ""
            while True:
                try:
                    msg_type, msg_data = chunk_queue.get(timeout=120.0)
                    if msg_type == "done":
                        break
                    if msg_type == "chunk" and msg_data:
                        if not first_chunk_emitted:
                            self._emit_lifecycle_event(
                                "provider_first_chunk",
                                request_id=request_id,
                            )
                            first_chunk_emitted = True
                        accumulated_text += msg_data
                        self.log_handler.log(
                            AgentStreamChunkEvent(
                                agent_name=self.name,
                                chunk_text=msg_data,
                                accumulated_text=accumulated_text,
                            )
                        )
                except queue.Empty:
                    break
            streaming_thread.join(timeout=5.0)

            if result_holder["error"] is not None:
                self._emit_lifecycle_event(
                    "provider_request_completed",
                    request_id=request_id,
                    metadata={"status": "failed"},
                )
                error = result_holder["error"]
                original_error = error
                if hasattr(error, "__class__") and error.__class__.__name__.endswith(
                    "ExceptionGroup"
                ):
                    if hasattr(error, "exceptions") and error.exceptions:
                        original_error = error.exceptions[0]
                error_str = str(original_error).lower()
                error_type = str(type(original_error).__name__)
                if "authenticationerror" in error_type.lower() or "api_key" in error_str:
                    from tactus.core.exceptions import TactusRuntimeError

                    raise TactusRuntimeError(
                        f"API authentication failed for agent '{self.name}': "
                        f"Missing or invalid API key. Please configure your API key in Settings (Cmd+,)."
                    ) from error
                if original_error is not error:
                    logger.error(
                        f"Agent '{self.name}' ExceptionGroup sub-exception: "
                        f"{type(original_error).__name__}: {original_error}"
                    )
                    raise RuntimeError(
                        f"Agent '{self.name}' failed: {type(original_error).__name__}: {original_error}"
                    ) from original_error
                raise result_holder["error"]

            if result_holder["result"] is None:
                self._emit_lifecycle_event(
                    "provider_request_completed",
                    request_id=request_id,
                    metadata={"status": "failed"},
                )
                raise RuntimeError("Streaming produced no result")
            self._emit_lifecycle_event(
                "provider_request_completed",
                request_id=request_id,
                metadata={"status": "completed"},
            )
            return result_holder["result"]

        if os.environ.get("PLEXUS_DEBUG_LLM"):
            self._log_llm_debug_input(prompt_context)

        self.log_handler.log(AgentTurnEvent(agent_name=self.name, stage="started"))

        new_messages: List[Dict[str, Any]] = []
        user_message = opts.get("message")
        if self._turn_count == 1 and not user_message and self.initial_message:
            user_message = self.initial_message
        if user_message:
            user_msg = {"role": "user", "content": user_message}
            new_messages.append(user_msg)
            self._history.add(user_msg)

        current_prompt_context = prompt_context
        forced_synthesis = False
        tool_followup_rounds = 0
        while True:
            try:
                dspy_result = _stream_once(current_prompt_context)
            except RuntimeError as error:
                if str(error) == "Streaming produced no result":
                    logger.warning(
                        f"Streaming produced no result for agent '{self.name}', falling back"
                    )
                    return self._turn_without_streaming(opts, prompt_context)
                raise

            if os.environ.get("PLEXUS_DEBUG_LLM"):
                self._log_llm_debug_output(dspy_result)

            assistant_text = getattr(dspy_result, "response", "")
            assistant_msg: Dict[str, Any] = {"role": "assistant", "content": assistant_text}
            tool_calls_list = self._to_tool_calls_list(dspy_result)
            if tool_calls_list:
                assistant_msg["tool_calls"] = tool_calls_list

            new_messages.append(assistant_msg)
            self._history.add(assistant_msg)

            tool_outcome = self._execute_assistant_tool_calls(assistant_msg, new_messages)
            if tool_outcome.had_tool_calls:
                if tool_outcome.terminal_done_called:
                    break
                tool_followup_rounds += 1
                if tool_followup_rounds > self.max_tool_followup_rounds:
                    raise RuntimeError(
                        f"Agent '{self.name}' exceeded max tool follow-up rounds "
                        f"({self.max_tool_followup_rounds}) without producing a final response"
                    )
                current_prompt_context = self._tool_followup_prompt_context(prompt_context)
                continue

            if self._is_usable_assistant_text(assistant_text):
                break

            if forced_synthesis:
                break
            forced_synthesis = True
            current_prompt_context = self._synthesis_prompt_context(prompt_context)

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
        if os.environ.get("PLEXUS_DEBUG_LLM"):
            self._log_llm_debug_input(prompt_context)

        new_messages: List[Dict[str, Any]] = []
        user_message = opts.get("message")
        if self._turn_count == 1 and not user_message and self.initial_message:
            user_message = self.initial_message
        if user_message:
            user_msg = {"role": "user", "content": user_message}
            new_messages.append(user_msg)
            self._history.add(user_msg)

        current_prompt_context = prompt_context
        forced_synthesis = False
        tool_followup_rounds = 0
        while True:
            request_id = self._provider_request_started(current_prompt_context)
            try:
                dspy_result = self._module.module(**current_prompt_context)
            except Exception:
                self._emit_lifecycle_event(
                    "provider_request_completed",
                    request_id=request_id,
                    metadata={"status": "failed"},
                )
                raise
            self._emit_lifecycle_event(
                "provider_request_completed",
                request_id=request_id,
                metadata={"status": "completed"},
            )
            if os.environ.get("PLEXUS_DEBUG_LLM"):
                self._log_llm_debug_output(dspy_result)

            assistant_text = getattr(dspy_result, "response", "")
            assistant_msg: Dict[str, Any] = {"role": "assistant", "content": assistant_text}
            tool_calls_list = self._to_tool_calls_list(dspy_result)
            if tool_calls_list:
                assistant_msg["tool_calls"] = tool_calls_list

            new_messages.append(assistant_msg)
            self._history.add(assistant_msg)

            tool_outcome = self._execute_assistant_tool_calls(assistant_msg, new_messages)
            if tool_outcome.had_tool_calls:
                if tool_outcome.terminal_done_called:
                    break
                tool_followup_rounds += 1
                if tool_followup_rounds > self.max_tool_followup_rounds:
                    raise RuntimeError(
                        f"Agent '{self.name}' exceeded max tool follow-up rounds "
                        f"({self.max_tool_followup_rounds}) without producing a final response"
                    )
                current_prompt_context = self._tool_followup_prompt_context(prompt_context)
                continue

            if self._is_usable_assistant_text(assistant_text):
                break

            if forced_synthesis:
                break
            forced_synthesis = True
            current_prompt_context = self._synthesis_prompt_context(prompt_context)

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
            "request_timeout",
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
        self._emit_lifecycle_event("agent_preparation_started")

        # Execute the turn (inlined from old turn() method)
        self._turn_count += 1
        logger.debug(f"Agent '{self.name}' turn {self._turn_count}")

        # Check for mock first (before any LLM calls)
        if self.mock_manager and self.registry:
            mock_response = self._get_mock_response(opts)
            if mock_response is not None:
                logger.debug(f"Agent '{self.name}' returning mock response")
                return mock_response

        # Extract options
        user_message = opts.get("message")

        # Use initial_message on first turn if no inject provided
        if self._turn_count == 1 and not user_message and self.initial_message:
            user_message = self.initial_message

        context = opts.get("context") or {}
        self._inject_pending_steering()

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

        self._emit_lifecycle_event("agent_preparation_completed")
        return self._turn_with_retries(opts, prompt_context)

    def _emit_lifecycle_event(
        self,
        phase: str,
        *,
        request_id: Optional[str] = None,
        prompt_context: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Emit a supported agent lifecycle event to configured observers."""
        from tactus.protocols.models import AgentLifecycleEvent

        event = AgentLifecycleEvent(
            agent_name=self.name,
            phase=phase,
            request_id=request_id,
            prompt_context=prompt_context,
            metadata=metadata or {},
        )
        if self.log_handler is not None:
            self.log_handler.log(event)
        for hook in self.lifecycle_hooks:
            hook(event)
        return event

    def _provider_request_started(self, prompt_context: Dict[str, Any]) -> str:
        self._model_request_count += 1
        request_id = f"{self.name}:{self._model_request_count}"
        self._emit_lifecycle_event(
            "provider_request_started",
            request_id=request_id,
            prompt_context=prompt_context,
        )
        return request_id

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

    def _inject_pending_steering(self) -> None:
        """Inject new procedure steering notes once per agent before the next LLM call."""
        if not self.steering_enabled:
            return
        chat_recorder = getattr(self, "chat_recorder", None)
        state_primitive = getattr(self, "_state_primitive", None)
        if not chat_recorder or not state_primitive:
            return

        get_messages = getattr(chat_recorder, "get_steering_messages", None)
        if not callable(get_messages):
            return

        watermark_key = f"procedure_steering_watermark:{self.name}"
        try:
            after = state_primitive.get(watermark_key) or ""
            result = get_messages(
                after=after,
                agent_name=self.name,
                limit=20,
            )
            messages = result.get("messages", []) if isinstance(result, dict) else []
            watermark = result.get("watermark") if isinstance(result, dict) else None
            if not messages:
                if watermark and watermark != after:
                    state_primitive.set(watermark_key, watermark)
                return

            lines = ["=== USER STEERING RECEIVED MID-RUN ==="]
            for index, message in enumerate(messages, start=1):
                created_at = message.get("created_at") or "unknown time"
                content = str(message.get("content") or "").strip()
                lines.append(f"{index}. [{created_at}] {content}")
            lines.append(
                "Treat this as advisory operator guidance for this and future procedure work."
            )
            lines.append("=== END USER STEERING ===")
            self._history.add({"role": "system", "content": "\n".join(lines)})
            state_primitive.set(
                watermark_key,
                watermark or messages[-1].get("created_at") or after,
            )
            logger.info(
                "Injected %d steering message(s) into agent '%s'",
                len(messages),
                self.name,
            )
        except Exception as exc:
            logger.warning(
                "Failed to inject procedure steering into agent '%s': %s",
                self.name,
                exc,
            )

    @staticmethod
    def _history_from_messages(messages: List[Dict[str, Any]]):
        return TactusHistory(messages=messages).to_dspy()

    def _turn_with_retries(
        self,
        opts: Dict[str, Any],
        prompt_context: Dict[str, Any],
    ) -> TactusResult:
        attempts = max(self.response_retries, 0) + 1
        if getattr(self, "retry_enabled", False):
            attempts = max(1, int(getattr(self, "retry_attempts", 1) or 1))
        history_length = len(self._history)

        for attempt in range(attempts):
            try:
                with self._dspy_lm_context(opts):
                    if self._should_stream():
                        logger.debug(f"Agent '{self.name}' using streaming mode")
                        result = self._turn_with_streaming(opts, prompt_context)
                    else:
                        logger.debug(f"Agent '{self.name}' using non-streaming mode")
                        result = self._turn_without_streaming(opts, prompt_context)

                self._validate_output(result)
                return result
            except Exception as error:
                # Never retry cancellation / shutdown signals.
                if isinstance(error, (KeyboardInterrupt, SystemExit, asyncio.CancelledError)):
                    raise

                if getattr(self, "retry_enabled", False):
                    # Decide if this exception is eligible for retry.
                    retry_on = getattr(self, "retry_on", "infra_plus_validation")
                    is_validation = isinstance(error, ValueError)
                    if retry_on == "infra_only" and is_validation:
                        raise
                    if retry_on == "validation_only" and not is_validation:
                        raise

                    # Authentication/config errors are not helped by retry.
                    err_l = str(error).lower()
                    if "api key" in err_l or "api_key" in err_l or "authentication" in err_l:
                        raise

                if attempt >= attempts - 1:
                    logger.debug("Agent '%s' turn failed: %s", self.name, error, exc_info=True)
                    raise
                self._history.truncate(history_length)

                delay = 0.0
                if getattr(self, "retry_enabled", False):
                    base = float(getattr(self, "retry_delay_seconds", 0.0) or 0.0)
                    if base > 0:
                        if getattr(self, "retry_backoff", "constant") == "exponential":
                            delay = base * (2**attempt)
                        else:
                            delay = base
                        max_d = float(getattr(self, "retry_max_delay_seconds", 0.0) or 0.0)
                        if max_d and delay > max_d:
                            delay = max_d
                        if getattr(self, "retry_jitter", False) and delay > 0:
                            delay = random.random() * delay
                else:
                    delay = float(self.response_retry_delay or 0.0)

                if delay > 0:
                    time.sleep(delay)

        raise RuntimeError("Unexpected retry loop exit")  # pragma: no cover

    def _agent_lm_config(self, opts: Optional[Dict[str, Any]] = None) -> tuple[str, Dict[str, Any]]:
        """Return the normalized model and LM kwargs for this agent turn."""
        opts = opts or {}
        model_for_litellm = _normalize_model_for_litellm(self.model, self.provider)
        config_kwargs: Dict[str, Any] = {}

        temperature = opts.get("temperature", self.temperature)
        max_tokens = opts.get("max_tokens", self.max_tokens)

        if temperature is not None:
            config_kwargs["temperature"] = temperature
        if max_tokens is not None:
            config_kwargs["max_tokens"] = max_tokens
        if self.model_type is not None:
            config_kwargs["model_type"] = self.model_type
        if self.reasoning_effort is not None:
            config_kwargs["reasoning_effort"] = self.reasoning_effort
        if self.verbosity is not None:
            config_kwargs["verbosity"] = self.verbosity
        request_timeout = opts.get("request_timeout", self.request_timeout)
        if request_timeout is not None:
            config_kwargs["request_timeout"] = request_timeout
        if self.tool_choice is not None and (self.tools or self.toolsets):
            config_kwargs["tool_choice"] = self.tool_choice

        return model_for_litellm, config_kwargs

    def _get_agent_lm(self, opts: Optional[Dict[str, Any]] = None) -> Any:
        """Create or reuse the LM configured for this agent, independent of DSPy globals."""
        from tactus.dspy.config import (
            create_adapter,
            create_lm,
            get_prewarmed_adapter,
            get_prewarmed_lm,
        )

        model_for_litellm, config_kwargs = self._agent_lm_config(opts)
        cache_key = (model_for_litellm, tuple(sorted(config_kwargs.items())))
        if self._agent_lm is None or self._agent_lm_key != cache_key:
            logger.debug(
                "Creating scoped DSPy LM for agent '%s' with model: %s",
                self.name,
                model_for_litellm,
            )
            self._agent_lm = get_prewarmed_lm(model_for_litellm, **config_kwargs)
            self._agent_adapter = get_prewarmed_adapter(model_for_litellm, **config_kwargs)
            if self._agent_lm is None:
                self._emit_lifecycle_event("lm_initialization_started")
                self._agent_lm = create_lm(model_for_litellm, **config_kwargs)
                self._agent_adapter = create_adapter()
                self._emit_lifecycle_event("lm_initialization_completed")
            elif self._agent_adapter is None:
                self._agent_adapter = create_adapter()
            self._agent_lm_key = cache_key
        return self._agent_lm

    def prewarm(self, opts: Optional[Dict[str, Any]] = None) -> Any:
        """Initialize this agent's LM client and adapter without making a request."""
        from tactus.dspy.config import prewarm_lm

        model_for_litellm, config_kwargs = self._agent_lm_config(opts)
        warmed = prewarm_lm(model_for_litellm, **config_kwargs)
        self._agent_lm = warmed.lm
        self._agent_adapter = warmed.adapter
        self._agent_lm_key = (model_for_litellm, tuple(sorted(config_kwargs.items())))
        return warmed

    def _dspy_lm_context(self, opts: Optional[Dict[str, Any]] = None):
        if not self.model:
            return nullcontext()

        lm = self._get_agent_lm(opts)
        return dspy.context(lm=lm, adapter=self._agent_adapter)

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
        reasoning_effort=config.get("reasoning_effort"),
        verbosity=config.get("verbosity"),
        request_timeout=config.get("request_timeout"),
        steering_enabled=config.get("steering_enabled", True),
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
                "reasoning_effort",
                "verbosity",
                "request_timeout",
                "steering_enabled",
                "module",
                "initial_message",
                "log_handler",
                "disable_streaming",
            ]
        },
    )


def prewarm_agent_runtime(
    model: str,
    *,
    provider: Optional[str] = None,
    **config: Any,
) -> Any:
    """Prewarm the Agent LM stack without making a provider request.

    The returned handle contains the configured LM and adapter. A later Agent
    with the same effective configuration reuses those prepared objects.
    """
    from tactus.dspy.config import prewarm_lm

    normalized_model = _normalize_model_for_litellm(model, provider)
    return prewarm_lm(normalized_model, **config)
