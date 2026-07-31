from typing import Optional, Union

import pytest

import dspy
from litellm import ModelResponseStream

from tactus.dspy.broker_lm import BrokeredLM


class _FakeBrokerClient:
    def llm_chat(
        self,
        *,
        provider: str,
        model: str,
        messages: list[dict],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        tools: Optional[list[dict]] = None,
        tool_choice: Optional[Union[dict, str]] = None,
        stream: bool,
        **kwargs,
    ):
        async def gen():
            if stream:
                yield {"event": "delta", "data": {"text": "he"}}
                yield {"event": "delta", "data": {"text": "llo"}}
                yield {
                    "event": "done",
                    "data": {
                        "text": "hello",
                        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                    },
                }
                return

            yield {
                "event": "done",
                "data": {
                    "text": "hello",
                    "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                },
            }

        return gen()


class _FakeSendStream:
    def __init__(self):
        self.items: list[object] = []

    async def send(self, item: object) -> None:
        self.items.append(item)


class _RecordingBrokerClient(_FakeBrokerClient):
    def __init__(self):
        self.calls: list[dict] = []

    def llm_chat(self, **kwargs):
        self.calls.append(kwargs)
        return super().llm_chat(**kwargs)


@pytest.mark.asyncio
async def test_brokered_lm_non_streaming_uses_broker_events():
    lm = BrokeredLM("openai/gpt-4o-mini", socket_path="unused.sock")
    lm._client = _FakeBrokerClient()  # type: ignore[assignment]

    resp = await lm.aforward(messages=[{"role": "user", "content": "hi"}])
    assert resp.choices[0].message.content == "hello"


@pytest.mark.asyncio
async def test_brokered_lm_forwards_num_retries_to_broker():
    lm = BrokeredLM("openai/gpt-4o-mini", socket_path="unused.sock", num_retries=0)
    client = _RecordingBrokerClient()
    lm._client = client  # type: ignore[assignment]

    await lm.aforward(messages=[{"role": "user", "content": "hi"}])

    assert len(client.calls) == 1
    assert client.calls[0]["num_retries"] == 0


@pytest.mark.asyncio
async def test_brokered_lm_streaming_sends_model_response_stream_chunks():
    lm = BrokeredLM("openai/gpt-4o-mini", socket_path="unused.sock")
    lm._client = _FakeBrokerClient()  # type: ignore[assignment]

    send_stream = _FakeSendStream()
    with dspy.settings.context(send_stream=send_stream):
        resp = await lm.aforward(messages=[{"role": "user", "content": "hi"}])

    chunks = [i for i in send_stream.items if isinstance(i, ModelResponseStream)]
    assert "".join(c.choices[0].delta.content for c in chunks) == "hello"
    assert resp.choices[0].message.content == "hello"
