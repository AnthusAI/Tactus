"""
LLM model backend for inference using language models.

This backend uses an Agent internally to handle LLM interactions.
It returns structured output that matches the stdlib LLM model schema.
"""

import json
import logging
from typing import Any, Dict, Optional

from tactus.dspy.agent import DSPyAgentHandle
from tactus.model_params import default_temperature_for_model
from tactus.protocols.cost import CostStats, UsageStats

logger = logging.getLogger(__name__)


class LLMModelBackend:
    """Model backend that uses LLM for classification/extraction tasks."""

    def __init__(
        self,
        model: str,
        system_prompt: str,
        provider: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        reasoning_effort: Optional[str] = None,
        verbosity: Optional[str] = None,
        mock_manager: Optional[Any] = None,
        registry: Optional[Any] = None,
        execution_context: Optional[Any] = None,
        **kwargs: Any,
    ):
        """
        Initialize LLM model backend.

        Args:
            model: Model name (in LiteLLM format, e.g., "openai/gpt-4o")
            system_prompt: System prompt for the classification task
            provider: Provider name (deprecated, use model instead)
            temperature: Model temperature. None applies a model-specific default:
                gpt-5 family omits temperature entirely; all others use 0.0.
            max_tokens: Maximum tokens for response
            reasoning_effort: Optional GPT-5-family reasoning effort control
            verbosity: Optional GPT-5-family response verbosity control
            mock_manager: Optional MockManager instance for testing
            registry: Optional Registry instance
            execution_context: Optional ExecutionContext (not used by internal Agent)
        """
        self.model = model
        self.system_prompt = system_prompt
        self.provider = provider
        # Apply model-specific default: gpt-5 family → None (omit from API);
        # all others → 0.0 (deterministic classification).
        if temperature is None:
            temperature = default_temperature_for_model(model)
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.reasoning_effort = reasoning_effort
        self.verbosity = verbosity
        self.mock_manager = mock_manager
        self.registry = registry
        # Note: execution_context not passed to Agent - we don't checkpoint internal turns

        # Create internal Agent for LLM interactions
        # Agent handles conversation, retry logic, and response parsing
        self._agent = DSPyAgentHandle(
            name=f"llm_backend_{model}",
            system_prompt=system_prompt,
            model=model,
            provider=provider,
            temperature=temperature,
            max_tokens=max_tokens,
            reasoning_effort=reasoning_effort,
            verbosity=verbosity,
            mock_manager=mock_manager,
            registry=registry,
            execution_context=None,  # Don't checkpoint internal agent turns
        )

        # Track cumulative costs across all predictions
        self._total_usage = UsageStats()
        self._total_cost = CostStats()

    async def predict(self, input_data: Any) -> Dict[str, Any]:
        """
        Run LLM inference on input data (async wrapper for sync implementation).

        Args:
            input_data: Input dict with fields for the classification/extraction task

        Returns:
            Dict with prediction result, cost, and usage stats
        """
        return self.predict_sync(input_data)

    def predict_sync(self, input_data: Any) -> Dict[str, Any]:
        """
        Run LLM inference on input data (synchronous version).

        Args:
            input_data: Input dict with fields for the classification/extraction task

        Returns:
            Dict with prediction result, cost, and usage stats:
            {
                "result": {"response": <raw text>},
                "cost": {"total": 0.001, "input": 0.0005, "output": 0.0005},
                "usage": {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150}
            }
        """
        # Convert input_data to message for Agent
        if isinstance(input_data, dict):
            message = json.dumps(input_data)
        else:
            message = str(input_data)

        # Call the internal Agent (sync call)
        agent_result = self._agent({"message": message})

        # Extract response text — return raw string for the caller to parse
        if isinstance(agent_result.output, dict):
            response_text = agent_result.output.get("response") or str(agent_result.output)
        else:
            response_text = str(agent_result.output)

        # Update cumulative stats
        self._update_stats(agent_result)

        return {
            "result": {"response": response_text},
            "cost": agent_result.cost_stats.model_dump(),
            "usage": agent_result.usage.model_dump(),
        }

    def _update_stats(self, agent_result: Any) -> None:
        """
        Update cumulative cost and usage stats.

        Args:
            agent_result: TactusResult from Agent call
        """
        # Accumulate usage stats
        self._total_usage.prompt_tokens += agent_result.usage.prompt_tokens
        self._total_usage.completion_tokens += agent_result.usage.completion_tokens
        self._total_usage.total_tokens += agent_result.usage.total_tokens

        # Accumulate cost stats
        self._total_cost.prompt_cost += agent_result.cost_stats.prompt_cost
        self._total_cost.completion_cost += agent_result.cost_stats.completion_cost
        self._total_cost.total_cost += agent_result.cost_stats.total_cost

    @property
    def usage(self) -> UsageStats:
        """Return cumulative token usage for this backend."""
        return self._total_usage

    @property
    def cost(self) -> CostStats:
        """Return cumulative cost for this backend."""
        return self._total_cost
