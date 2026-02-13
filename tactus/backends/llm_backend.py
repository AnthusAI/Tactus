"""
LLM model backend for inference using language models.

This backend uses an Agent internally to handle LLM interactions,
including retry logic, response parsing, and error handling.
The Agent presents the Model's stateless predict() interface to callers.
"""

import asyncio
import json
import logging
from typing import Any, Dict, Optional

from tactus.dspy.agent import DSPyAgentHandle
from tactus.protocols.cost import CostStats, UsageStats

logger = logging.getLogger(__name__)


class LLMModelBackend:
    """Model backend that uses LLM for classification/extraction tasks."""

    def __init__(
        self,
        model: str,
        system_prompt: str,
        provider: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
        retries: int = 3,
        retry_prompt: Optional[str] = None,
        parse_direction: str = "end",
        mock_manager: Optional[Any] = None,
        registry: Optional[Any] = None,
        execution_context: Optional[Any] = None,
    ):
        """
        Initialize LLM model backend.

        Args:
            model: Model name (in LiteLLM format, e.g., "openai/gpt-4o")
            system_prompt: System prompt describing the classification/extraction task
            provider: Provider name (deprecated, use model instead)
            temperature: Model temperature (default: 0.0 for deterministic classification)
            max_tokens: Maximum tokens for response
            retries: Number of retry attempts for invalid responses (default: 3)
            retry_prompt: Prompt to use on retry (default: "Invalid response. Please try again.")
            parse_direction: Direction to parse response ("start" or "end", default: "end")
                - "end": Parse from end (for chain-of-thought reasoning)
                - "start": Parse from start (for fine-tuned models)
            mock_manager: Optional MockManager instance for testing
            registry: Optional Registry instance
            execution_context: Optional ExecutionContext (not used by internal Agent)
        """
        self.model = model
        self.system_prompt = system_prompt
        self.provider = provider
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.retries = retries
        self.retry_prompt = retry_prompt or "Invalid response. Please try again."
        self.parse_direction = parse_direction
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
                "result": <parsed output>,
                "cost": {"total": 0.001, "input": 0.0005, "output": 0.0005},
                "usage": {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150}
            }
        """
        # Convert input_data to message for Agent
        if isinstance(input_data, dict):
            message = json.dumps(input_data)
        else:
            message = str(input_data)

        # Call Agent with retry logic
        result = None
        last_error = None

        for attempt in range(self.retries + 1):
            try:
                # Call the internal Agent (sync call)
                agent_result = self._agent({"message": message})

                # Extract response text
                # Agent returns TactusResult with output field (either string or dict)
                if isinstance(agent_result.output, dict):
                    response_text = agent_result.output.get("response", "")
                else:
                    response_text = str(agent_result.output)

                # Parse the response based on parse_direction
                parsed_result = self._parse_response(response_text)

                # Update cumulative stats
                self._update_stats(agent_result)

                # Return with cost and usage
                return {
                    "result": parsed_result,
                    "cost": agent_result.cost_stats.model_dump(),
                    "usage": agent_result.usage.model_dump(),
                }

            except (json.JSONDecodeError, ValueError, KeyError) as e:
                last_error = e
                logger.warning(
                    f"LLM backend parse error (attempt {attempt + 1}/{self.retries + 1}): {e}"
                )

                if attempt < self.retries:
                    # Retry with feedback
                    message = self.retry_prompt
                else:
                    # Out of retries
                    raise ValueError(
                        f"LLM backend failed to produce valid output after {self.retries + 1} attempts. "
                        f"Last error: {last_error}"
                    ) from last_error

    def _parse_response(self, response_text: str) -> Any:
        """
        Parse LLM response text to extract structured output.

        Args:
            response_text: Raw response from LLM

        Returns:
            Parsed result (dict, list, or primitive)

        Raises:
            json.JSONDecodeError: If response is not valid JSON
            ValueError: If response format is invalid
        """
        if self.parse_direction == "start":
            # Parse from start (fine-tuned models)
            # Look for JSON at the beginning of the response
            response_text = response_text.strip()
            if response_text.startswith("{") or response_text.startswith("["):
                # Find the end of the JSON
                try:
                    return json.loads(response_text)
                except json.JSONDecodeError:
                    # Try to find the first complete JSON object/array
                    for i in range(len(response_text), 0, -1):
                        try:
                            return json.loads(response_text[:i])
                        except json.JSONDecodeError:
                            continue
                    raise ValueError("No valid JSON found at start of response")
            else:
                raise ValueError("Response does not start with JSON")
        else:
            # Parse from end (chain-of-thought reasoning)
            # Look for JSON at the end of the response
            response_text = response_text.strip()
            if response_text.endswith("}") or response_text.endswith("]"):
                # Find the start of the JSON
                try:
                    return json.loads(response_text)
                except json.JSONDecodeError:
                    # Try to find the last complete JSON object/array
                    for i in range(len(response_text)):
                        try:
                            return json.loads(response_text[i:])
                        except json.JSONDecodeError:
                            continue
                    raise ValueError("No valid JSON found at end of response")
            else:
                raise ValueError("Response does not end with JSON")

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
