"""ResponsesChatLM: chat requests with tools go to the Responses API and come back as chat completions."""

import json

import pytest

from tactus.dspy import config
from tactus.dspy.responses_lm import (
    ResponsesChatLM,
    chat_completion_from_response,
    responses_request_from_chat_request,
)
from tactus.model_params import default_temperature_for_model, uses_responses_api_by_default

TOOL = {
    "type": "function",
    "function": {
        "name": "fetch_pdf_text",
        "description": "Read a PDF.",
        "parameters": {
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
    },
}
CONVERSATION = [
    {"role": "system", "content": "Follow the skill."},
    {"role": "user", "content": "Read the opinion."},
    {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": "fetch_pdf_text", "arguments": '{"url": "u"}'},
            }
        ],
    },
    {"role": "tool", "tool_call_id": "call_1", "content": "page one"},
]


def test_the_whole_conversation_keeps_its_tool_calls_and_results():
    request = responses_request_from_chat_request(
        "openai/gpt-6-luna",
        CONVERSATION,
        {"tools": [TOOL], "max_tokens": 900, "cache": False, "n": 1},
    )

    assert request["input"] == [
        {"role": "system", "content": "Follow the skill."},
        {"role": "user", "content": "Read the opinion."},
        {
            "type": "function_call",
            "call_id": "call_1",
            "name": "fetch_pdf_text",
            "arguments": '{"url": "u"}',
        },
        {"type": "function_call_output", "call_id": "call_1", "output": "page one"},
    ]
    assert request["tools"] == [
        {
            "type": "function",
            "name": "fetch_pdf_text",
            "description": "Read a PDF.",
            "parameters": TOOL["function"]["parameters"],
        }
    ]
    assert request["max_output_tokens"] == 900 and "cache" not in request and "n" not in request


def test_reasoning_verbosity_tool_choice_and_format_use_responses_fields():
    request = responses_request_from_chat_request(
        "openai/gpt-6-luna",
        [{"role": "user", "content": "x"}],
        {
            "reasoning_effort": "medium",
            "verbosity": "low",
            "tool_choice": {"type": "function", "function": {"name": "done"}},
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "out", "schema": {"type": "object"}},
            },
            "headers": {"x-trace": "1"},
        },
    )

    assert request["reasoning"] == {"effort": "medium"}
    assert request["text"] == {
        "verbosity": "low",
        "format": {"type": "json_schema", "name": "out", "schema": {"type": "object"}},
    }
    assert request["tool_choice"] == {"type": "function", "name": "done"}
    assert request["extra_headers"] == {"x-trace": "1"}


def test_function_calls_and_text_come_back_as_a_chat_completion():
    response = {
        "id": "resp_1",
        "model": "gpt-6-luna",
        "status": "completed",
        "output": [
            {"type": "reasoning", "summary": []},
            {"type": "message", "content": [{"type": "output_text", "text": "Reading it."}]},
            {
                "type": "function_call",
                "call_id": "call_2",
                "name": "done",
                "arguments": '{"reason": "ok"}',
            },
        ],
        "usage": {"input_tokens": 120, "output_tokens": 30},
    }

    completion = chat_completion_from_response(response, "openai/gpt-6-luna")

    choice = completion.choices[0]
    assert choice.finish_reason == "tool_calls" and choice.message.content == "Reading it."
    call = choice.message.tool_calls[0]
    assert (
        call.id == "call_2"
        and call.function.name == "done"
        and json.loads(call.function.arguments) == {"reason": "ok"}
    )
    assert completion.usage.prompt_tokens == 120 and completion.usage.total_tokens == 150


def test_an_incomplete_response_reports_truncation():
    completion = chat_completion_from_response(
        {"status": "incomplete", "output": []}, "openai/gpt-6-luna"
    )
    assert completion.choices[0].finish_reason == "length"


def test_gpt6_models_use_the_responses_api_and_no_temperature():
    assert uses_responses_api_by_default("openai/gpt-6-luna")
    assert not uses_responses_api_by_default("openai/gpt-5.4")
    assert default_temperature_for_model("openai/gpt-6-luna") is None

    assert isinstance(config.language_model("openai/gpt-6-luna", {"cache": False}), ResponsesChatLM)
    assert isinstance(
        config.language_model("openai/gpt-5.4", {"cache": False, "model_type": "responses"}),
        ResponsesChatLM,
    )
    assert not isinstance(
        config.language_model("openai/gpt-5.4", {"cache": False}), ResponsesChatLM
    )


def test_forward_sends_one_responses_call(monkeypatch):
    import litellm

    calls = []

    def responses(**request):
        calls.append(request)
        return {
            "status": "completed",
            "output": [{"type": "message", "content": [{"type": "output_text", "text": "hi"}]}],
        }

    monkeypatch.setattr(litellm, "responses", responses)
    lm = ResponsesChatLM("openai/gpt-6-luna", cache=False)

    result = lm.forward(messages=[{"role": "user", "content": "hello"}], tools=[TOOL])

    assert (
        calls[0]["model"] == "openai/gpt-6-luna"
        and calls[0]["tools"][0]["name"] == "fetch_pdf_text"
    )
    assert result.choices[0].message.content == "hi"
    assert result._hidden_params["_response_ms"] >= 0


@pytest.mark.asyncio
async def test_aforward_sends_one_async_responses_call(monkeypatch):
    import litellm

    async def aresponses(**request):
        return {
            "status": "completed",
            "output": [
                {"type": "function_call", "call_id": "c", "name": "done", "arguments": "{}"}
            ],
        }

    monkeypatch.setattr(litellm, "aresponses", aresponses)
    result = await ResponsesChatLM("openai/gpt-6-luna", cache=False).aforward(
        messages=[{"role": "user", "content": "x"}]
    )

    assert result.choices[0].message.tool_calls[0].function.name == "done"
