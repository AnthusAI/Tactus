"""
DSPy LM implementation backed by the local Tactus broker.

This allows the runtime container to be:
- networkless (`--network none`)
- secretless (no API keys in env/mounts/request payload)

while still supporting streaming via DSPy's `streamify()` mechanism.
"""

from __future__ import annotations

import logging
from typing import Any

import dspy
import litellm
from asyncer import syncify
from litellm import ModelResponse, ModelResponseStream

from tactus.broker.client import BrokerClient

logger = logging.getLogger(__name__)


def _split_provider_model(model: str) -> tuple[str, str]:
    if "/" not in model:
        raise ValueError(f"Invalid model format: {model}. Expected 'provider/model'.")
    provider, model_id = model.split("/", 1)
    return provider, model_id


class BrokeredLM(dspy.BaseLM):
    """
    A DSPy-compatible LM that delegates completion calls to the broker.

    The broker connection is configured via `TACTUS_BROKER_SOCKET`.
    """

    def __init__(
        self,
        model: str,
        *,
        model_type: str = "chat",
        temperature: float | None = None,
        max_tokens: int | None = None,
        cache: bool | None = None,
        socket_path: str | None = None,
        **kwargs: Any,
    ):
        if model_type != "chat":
            raise ValueError("BrokeredLM currently supports only model_type='chat'")

        super().__init__(
            model=model,
            model_type=model_type,
            temperature=temperature if temperature is not None else 0.7,
            max_tokens=max_tokens if max_tokens is not None else 1000,
            cache=False,
            **kwargs,
        )

        if socket_path is not None:
            self._client = BrokerClient(socket_path)
            return

        env_client = BrokerClient.from_environment()
        if env_client is None:
            raise RuntimeError("BrokerClient not configured (TACTUS_BROKER_SOCKET is missing)")
        self._client = env_client

    def forward(
        self, prompt: str | None = None, messages: list[dict[str, Any]] | None = None, **kwargs: Any
    ):
        return syncify(self.aforward)(prompt=prompt, messages=messages, **kwargs)

    async def aforward(
        self, prompt: str | None = None, messages: list[dict[str, Any]] | None = None, **kwargs: Any
    ):
        provider, model_id = _split_provider_model(self.model)

        if provider != "openai":
            raise ValueError(
                f"BrokeredLM only supports provider 'openai' for now (got {provider!r})"
            )

        if messages is None:
            if prompt is None:
                messages = []
            else:
                messages = [{"role": "user", "content": prompt}]

        merged_kwargs = {**self.kwargs, **kwargs}
        temperature = merged_kwargs.get("temperature")

        # DSPy uses `max_tokens`, while some reasoning models use `max_completion_tokens`.
        max_tokens = merged_kwargs.get("max_tokens")
        if max_tokens is None and merged_kwargs.get("max_completion_tokens") is not None:
            max_tokens = merged_kwargs.get("max_completion_tokens")

        send_stream = dspy.settings.send_stream
        caller_predict = dspy.settings.caller_predict
        caller_predict_id = id(caller_predict) if caller_predict else None

        # Extract tools and tool_choice from kwargs
        tools = merged_kwargs.get("tools")
        tool_choice = merged_kwargs.get("tool_choice")

        logger.debug(
            f"[BROKER_LM] Calling LM with streaming={send_stream is not None}, tools={len(tools) if tools else 0}"
        )
        if send_stream is not None:
            chunks: list[ModelResponseStream] = []
            tool_calls_data = None
            async for event in self._client.llm_chat(
                provider="openai",
                model=model_id,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
                tools=tools,
                tool_choice=tool_choice,
            ):
                event_type = event.get("event")
                if event_type == "delta":
                    text = (event.get("data") or {}).get("text") or ""
                    if not text:
                        continue
                    chunk = ModelResponseStream(
                        model=model_id,
                        choices=[{"index": 0, "delta": {"content": text}}],
                    )
                    if caller_predict_id is not None:
                        chunk.predict_id = caller_predict_id  # type: ignore[attr-defined]
                    chunks.append(chunk)
                    await send_stream.send(chunk)
                    continue

                if event_type == "done":
                    # Capture tool calls from done event
                    data = event.get("data") or {}
                    tool_calls_data = data.get("tool_calls")
                    logger.debug(
                        f"[BROKER_LM] Stream complete with {len(tool_calls_data) if tool_calls_data else 0} tool calls"
                    )
                    break

                if event_type == "error":
                    err = event.get("error") or {}
                    raise RuntimeError(err.get("message") or "Broker LLM error")

            # Build response manually to ensure tool_calls stay as plain dicts
            # (stream_chunk_builder might convert them to typed objects)
            full_text = ""
            if chunks:
                final_response = litellm.stream_chunk_builder(chunks)
                if final_response.choices:
                    message = (
                        final_response.choices[0].get("message")
                        if isinstance(final_response.choices[0], dict)
                        else getattr(final_response.choices[0], "message", None)
                    )
                    if message:
                        full_text = (
                            message.get("content")
                            if isinstance(message, dict)
                            else getattr(message, "content", "") or ""
                        )

            message_data = {"role": "assistant", "content": full_text}
            finish_reason = "stop"

            if tool_calls_data:
                # Keep tool calls as plain dictionaries (already in OpenAI format from broker)
                message_data["tool_calls"] = tool_calls_data
                finish_reason = "tool_calls"

            return ModelResponse(
                model=model_id,
                choices=[
                    {
                        "index": 0,
                        "finish_reason": finish_reason,
                        "message": message_data,
                    }
                ],
                usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            )

        # Non-streaming path
        final_text = ""
        tool_calls_data = None
        usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        async for event in self._client.llm_chat(
            provider="openai",
            model=model_id,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=False,
            tools=tools,
            tool_choice=tool_choice,
        ):
            event_type = event.get("event")
            if event_type == "done":
                data = event.get("data") or {}
                final_text = data.get("text") or ""
                tool_calls_data = data.get("tool_calls")
                usage = data.get("usage") or usage
                break
            if event_type == "error":
                err = event.get("error") or {}
                raise RuntimeError(err.get("message") or "Broker LLM error")

        # Build message response with tool calls if present
        message_data = {"role": "assistant", "content": final_text}
        if tool_calls_data:
            # Keep tool calls as plain dictionaries (already in OpenAI format from broker)
            message_data["tool_calls"] = tool_calls_data

        return ModelResponse(
            model=model_id,
            choices=[
                {
                    "index": 0,
                    "finish_reason": "tool_calls" if tool_calls_data else "stop",
                    "message": message_data,
                }
            ],
            usage=usage,
        )
