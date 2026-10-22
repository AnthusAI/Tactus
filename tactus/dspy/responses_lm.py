"""A DSPy LM that talks to the OpenAI Responses API and answers in chat-completion form.

DSPy's own ``model_type="responses"`` flattens a conversation into one message, drops tool calls and
tool results, sends tool definitions in chat format and returns tool calls in Responses format, so an
agent with tools cannot run on it. Some models (the GPT-6 family) accept function tools only on the
Responses API. ``ResponsesChatLM`` converts the whole chat request (messages, tool calls, tool results,
tools, tool choice, reasoning and output controls) to a Responses request, and the response back to a
chat completion, so the ChatAdapter's native function calling and the rest of Tactus are unchanged.
"""

from __future__ import annotations

import json
import time
from typing import Any, Optional

import dspy

CHAT_ONLY_REQUEST_KEYS = ("n", "rollout_id", "cache")


def _text_of(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            str(item.get("text") or "")
            for item in content
            if isinstance(item, dict) and item.get("type") == "text"
        )
    return str(content)


def _input_content(content: Any, *, role: str) -> Any:
    if not isinstance(content, list):
        return _text_of(content)
    text_type = "output_text" if role == "assistant" else "input_text"
    converted = []
    for item in content:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "text":
            converted.append({"type": text_type, "text": item.get("text") or ""})
        elif item.get("type") == "image_url":
            image = item.get("image_url")
            converted.append(
                {
                    "type": "input_image",
                    "image_url": image.get("url") if isinstance(image, dict) else image,
                }
            )
        else:
            converted.append(item)
    return converted


def responses_input_from_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Every chat message becomes Responses input: tool calls and tool results keep their call ids."""
    items: list[dict[str, Any]] = []
    for message in messages:
        role = message.get("role") or "user"
        if role == "tool":
            items.append(
                {
                    "type": "function_call_output",
                    "call_id": message.get("tool_call_id"),
                    "output": _text_of(message.get("content")),
                }
            )
            continue
        content = message.get("content")
        if content not in (None, "", []):
            items.append({"role": role, "content": _input_content(content, role=role)})
        for call in message.get("tool_calls") or []:
            function = call.get("function") or {}
            arguments = function.get("arguments")
            items.append(
                {
                    "type": "function_call",
                    "call_id": call.get("id"),
                    "name": function.get("name"),
                    "arguments": (
                        arguments if isinstance(arguments, str) else json.dumps(arguments or {})
                    ),
                }
            )
    return items


def responses_tools_from_chat_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    converted = []
    for tool in tools or []:
        if tool.get("type") == "function" and isinstance(tool.get("function"), dict):
            function = tool["function"]
            converted.append(
                {
                    "type": "function",
                    "name": function.get("name"),
                    "description": function.get("description") or "",
                    "parameters": function.get("parameters")
                    or {"type": "object", "properties": {}},
                    **({"strict": function["strict"]} if "strict" in function else {}),
                }
            )
        else:
            converted.append(tool)
    return converted


def responses_request_from_chat_request(
    model: str, messages: list[dict[str, Any]], request: dict[str, Any]
) -> dict[str, Any]:
    request = {key: value for key, value in request.items() if key not in CHAT_ONLY_REQUEST_KEYS}
    converted: dict[str, Any] = {"model": model, "input": responses_input_from_messages(messages)}
    if "tools" in request:
        converted["tools"] = responses_tools_from_chat_tools(request.pop("tools"))
    if "tool_choice" in request:
        choice = request.pop("tool_choice")
        if isinstance(choice, dict) and isinstance(choice.get("function"), dict):
            choice = {"type": "function", "name": choice["function"].get("name")}
        converted["tool_choice"] = choice
    for chat_key in ("max_tokens", "max_completion_tokens"):
        if chat_key in request:
            value = request.pop(chat_key)
            if value is not None:
                converted["max_output_tokens"] = value
    if "reasoning_effort" in request:
        converted["reasoning"] = {
            **(request.pop("reasoning", None) or {}),
            "effort": request.pop("reasoning_effort"),
        }
    text = dict(request.pop("text", None) or {})
    if "verbosity" in request:
        text["verbosity"] = request.pop("verbosity")
    if "response_format" in request:
        response_format = request.pop("response_format")
        if isinstance(response_format, type):
            response_format = {
                "type": "json_schema",
                "name": response_format.__name__,
                "schema": response_format.model_json_schema(),
            }
        elif isinstance(response_format, dict) and isinstance(
            response_format.get("json_schema"), dict
        ):
            response_format = {"type": "json_schema", **response_format["json_schema"]}
        text["format"] = response_format
    if text:
        converted["text"] = text
    if "headers" in request:
        converted["extra_headers"] = request.pop("headers")
    converted.update(request)
    return converted


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def chat_completion_from_response(response: Any, model: str):
    """The Responses output as a LiteLLM ModelResponse with one choice."""
    from litellm import ModelResponse
    from litellm.types.utils import ChatCompletionMessageToolCall, Choices, Function, Message, Usage

    texts, tool_calls = [], []
    for item in _field(response, "output", None) or []:
        item_type = _field(item, "type")
        if item_type == "message":
            for part in _field(item, "content", None) or []:
                if _field(part, "type") in ("output_text", "text"):
                    texts.append(_field(part, "text", "") or "")
        elif item_type == "function_call":
            tool_calls.append(
                ChatCompletionMessageToolCall(
                    id=_field(item, "call_id") or _field(item, "id"),
                    type="function",
                    function=Function(
                        name=_field(item, "name"), arguments=_field(item, "arguments") or "{}"
                    ),
                )
            )
    incomplete = _field(response, "status") == "incomplete"
    finish_reason = "length" if incomplete else "tool_calls" if tool_calls else "stop"
    message = Message(
        content="".join(texts) or None, role="assistant", tool_calls=tool_calls or None
    )
    usage = _field(response, "usage", None)
    input_tokens = int(_field(usage, "input_tokens", 0) or 0)
    output_tokens = int(_field(usage, "output_tokens", 0) or 0)
    return ModelResponse(
        id=_field(response, "id"),
        model=_field(response, "model") or model,
        choices=[Choices(index=0, message=message, finish_reason=finish_reason)],
        usage=Usage(
            prompt_tokens=input_tokens,
            completion_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
        ),
    )


class ResponsesChatLM(dspy.LM):
    """A chat-model LM for DSPy whose requests go to the Responses API (see the module docstring)."""

    def __init__(self, model: str, **kwargs: Any):
        kwargs.pop("model_type", None)
        super().__init__(model, model_type="chat", **kwargs)

    def _request(
        self,
        prompt: Optional[str],
        messages: Optional[list[dict[str, Any]]],
        kwargs: dict[str, Any],
    ):
        messages = messages or [{"role": "user", "content": prompt}]
        return responses_request_from_chat_request(self.model, messages, {**self.kwargs, **kwargs})

    def _record_usage(self, result) -> None:
        if dspy.settings.usage_tracker and getattr(result, "usage", None):
            dspy.settings.usage_tracker.add_usage(self.model, dict(result.usage))

    def forward(
        self,
        prompt: Optional[str] = None,
        messages: Optional[list[dict[str, Any]]] = None,
        **kwargs: Any,
    ):
        import litellm

        started = time.monotonic()
        response = litellm.responses(
            **self._request(prompt, messages, kwargs), num_retries=self.num_retries
        )
        result = chat_completion_from_response(response, self.model)
        result._hidden_params["_response_ms"] = (time.monotonic() - started) * 1000
        self._check_truncation(result)
        self._record_usage(result)
        return result

    async def aforward(
        self,
        prompt: Optional[str] = None,
        messages: Optional[list[dict[str, Any]]] = None,
        **kwargs: Any,
    ):
        import litellm

        started = time.monotonic()
        response = await litellm.aresponses(
            **self._request(prompt, messages, kwargs), num_retries=self.num_retries
        )
        result = chat_completion_from_response(response, self.model)
        result._hidden_params["_response_ms"] = (time.monotonic() - started) * 1000
        self._check_truncation(result)
        self._record_usage(result)
        return result
