"""
Result primitive - wrapper around pydantic-ai's RunResult.

Provides Lua-accessible interface to RunResult data, usage stats, and messages.
Aligned with pydantic-ai's RunResult API.
"""

from typing import Any, Dict, List

try:
    from pydantic_ai.result import RunResult
    from pydantic_ai.messages import ModelMessage
except ImportError:
    # Fallback if pydantic_ai not available
    RunResult = Any
    ModelMessage = dict


class ResultPrimitive:
    """
    Wrapper around pydantic-ai's RunResult for Lua access.

    Provides access to:
    - result.data - The response (text or structured data)
    - result.usage - Token usage stats
    - result.new_messages() - Messages from this turn
    - result.all_messages() - Full conversation history

    Aligned with pydantic-ai's RunResult API.
    """

    def __init__(self, pydantic_result: RunResult):
        """
        Initialize Result primitive.

        Args:
            pydantic_result: The pydantic-ai RunResult object
        """
        self._result = pydantic_result

    @property
    def text(self) -> str:
        """
        Extract plain text content from the response.

        For plain text responses (no structured output), extracts the text
        from the underlying ModelResponse. For structured outputs, returns string representation.

        Returns:
            Plain text content from the response
        """
        # If we have streamed text (from IDE streaming mode), return that
        if hasattr(self, "_streamed_text") and self._streamed_text:
            return self._streamed_text

        # AgentRunResult has 'response' attribute which is a ModelResponse
        if hasattr(self._result, "response"):
            response = self._result.response

            # If it's a ModelResponse object, extract text from parts
            if hasattr(response, "parts"):
                text_parts = []
                for part in response.parts:
                    if hasattr(part, "content"):
                        text_parts.append(str(part.content))
                    elif hasattr(part, "text"):
                        text_parts.append(part.text)
                return "".join(text_parts)

        # Try 'output' attribute (for structured outputs)
        if hasattr(self._result, "output"):
            output = self._result.output

            # If it's a dict, return JSON
            if isinstance(output, dict):
                import json

                return json.dumps(output, indent=2)

            # If it's a Pydantic model, convert to dict then JSON
            if hasattr(output, "model_dump"):
                import json

                return json.dumps(output.model_dump(), indent=2)

            # If it's a string, return it
            if isinstance(output, str):
                return output

        # Fallback: use the .data property
        return str(self.data)

    @property
    def data(self) -> Any:
        """
        Get the response data (output).

        For text responses, returns a string.
        For structured outputs, returns a dict.

        Aligned with pydantic-ai's result.data

        Returns:
            Response data from the agent
        """
        # Access the response data
        if hasattr(self._result, "data"):
            data = self._result.data

            # Convert Pydantic models to dicts for Lua
            if hasattr(data, "model_dump"):
                result = data.model_dump()
                return result
            elif hasattr(data, "dict"):
                return data.dict()
            else:
                return data
        else:
            # Fallback to response attribute
            return str(self._result.response) if hasattr(self._result, "response") else None

    @property
    def usage(self) -> Dict[str, int]:
        """
        Get token usage statistics.

        Aligned with pydantic-ai's result.usage()

        Returns:
            Dict with prompt_tokens, completion_tokens, total_tokens
        """
        try:
            usage_obj = self._result.usage()
            return {
                "prompt_tokens": usage_obj.request_tokens or 0,
                "completion_tokens": usage_obj.response_tokens or 0,
                "total_tokens": usage_obj.total_tokens or 0,
            }
        except Exception:
            # Fallback if usage not available
            return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    def cost(self) -> Dict[str, int]:
        """
        Get estimated cost information.

        Note: pydantic-ai doesn't provide cost calculation directly.
        Returns usage stats for now - users can calculate cost based on model pricing.

        Returns:
            Dict with token usage (same as .usage)
        """
        return self.usage

    def new_messages(self) -> List[Dict[str, Any]]:
        """
        Get messages from this turn only.

        Aligned with pydantic-ai's result.new_messages()

        Returns:
            List of message dicts with 'role' and 'content' keys
        """
        try:
            messages = self._result.new_messages()
            return [self._convert_message(m) for m in messages]
        except Exception:
            return []

    def all_messages(self) -> List[Dict[str, Any]]:
        """
        Get full conversation history.

        Aligned with pydantic-ai's result.all_messages()

        Returns:
            List of message dicts with 'role' and 'content' keys
        """
        try:
            messages = self._result.all_messages()
            return [self._convert_message(m) for m in messages]
        except Exception:
            return []

    def extract_tracing_data(self) -> Dict[str, Any]:
        """
        Extract all available tracing/metadata from RunResult.

        Returns comprehensive dict of all available metrics for cost reporting.
        """
        data = {}

        # Check all common RunResult attributes
        attrs_to_check = [
            "request_id",
            "run_id",
            "session_id",
            "retry_count",
            "validation_errors",
            "attempts",
            "cache_hit",
            "cache_tokens",
            "cached_tokens",
            "latency_ms",
            "time_to_first_token",
            "finish_reason",
            "stop_reason",
            "model_version",
            "model_id",
            "temperature",
            "max_tokens",
            "top_p",
            "frequency_penalty",
            "logprobs",
            "top_logprobs",
            "system_fingerprint",
        ]

        for attr in attrs_to_check:
            if hasattr(self._result, attr):
                value = getattr(self._result, attr)
                if value is not None:
                    data[attr] = value

        # Check usage object for additional fields
        try:
            usage = self._result.usage()
            usage_attrs = ["cache_tokens", "cache_read_tokens", "cache_write_tokens"]
            for attr in usage_attrs:
                if hasattr(usage, attr):
                    value = getattr(usage, attr)
                    if value is not None and value > 0:
                        data[f"usage_{attr}"] = value
        except Exception:
            pass

        return data

    def _convert_message(self, msg: ModelMessage) -> Dict[str, Any]:
        """
        Convert pydantic-ai ModelMessage to Lua-friendly dict.

        Args:
            msg: ModelMessage object

        Returns:
            Dict with 'role' and 'content' keys
        """
        if isinstance(msg, dict):
            return {"role": msg.get("role", ""), "content": str(msg.get("content", ""))}
        else:
            # Handle pydantic_ai ModelMessage objects
            try:
                return {
                    "role": getattr(msg, "role", ""),
                    "content": str(getattr(msg, "content", "")),
                }
            except Exception:
                # Fallback: convert to string
                return {"role": "unknown", "content": str(msg)}
