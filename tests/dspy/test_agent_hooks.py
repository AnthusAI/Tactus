from types import MethodType

from tactus.dspy.agent import DSPyAgentHandle
from tactus.protocols.result import TactusResult


def test_prepare_hook_resolves_system_prompt():
    captured = {}

    def prepare_hook():
        return {"value": "ok"}

    agent = DSPyAgentHandle(
        name="worker",
        system_prompt="Context: {prepared.value}",
        model=None,
        module="Raw",
        prepare=prepare_hook,
    )

    def fake_turn(self, opts, prompt_context):
        captured["prompt"] = prompt_context["system_prompt"]
        return TactusResult(output="ok")

    agent._turn_without_streaming = MethodType(fake_turn, agent)

    agent._execute_turn({"message": "hello"})

    assert captured["prompt"] == "Context: ok"


def test_per_turn_system_prompt_override():
    captured = {}

    agent = DSPyAgentHandle(
        name="worker",
        system_prompt="Default template {params.x}",
        model=None,
        module="Raw",
    )

    def fake_turn(self, opts, prompt_context):
        captured["prompt"] = prompt_context["system_prompt"]
        return TactusResult(output="ok")

    agent._turn_without_streaming = MethodType(fake_turn, agent)

    agent._execute_turn(
        {
            "message": "hello",
            "system_prompt": "Override {params.x}",
            "context": {"x": "1"},
        }
    )

    assert captured["prompt"] == "Override 1"


def test_message_history_filter_applied():
    captured = {}

    agent = DSPyAgentHandle(
        name="worker",
        system_prompt="test",
        model=None,
        module="Raw",
        message_history_filter=("last_n", 1),
    )

    agent._history.add({"role": "user", "content": "first"})
    agent._history.add({"role": "assistant", "content": "second"})

    def fake_turn(self, opts, prompt_context):
        captured["history"] = prompt_context["history"].messages
        return TactusResult(output="ok")

    agent._turn_without_streaming = MethodType(fake_turn, agent)

    agent._execute_turn({"message": "hello"})

    assert len(captured["history"]) == 1
    assert captured["history"][0]["content"] == "second"


def test_response_retry_truncates_history():
    attempts = {"count": 0}

    agent = DSPyAgentHandle(
        name="worker",
        system_prompt="test",
        model=None,
        module="Raw",
        response={"retries": 1, "retry_delay": 0.0},
    )

    def fake_turn(self, opts, prompt_context):
        attempts["count"] += 1
        if attempts["count"] == 1:
            self._history.add({"role": "user", "content": "temp"})
            raise ValueError("bad response")
        self._history.add({"role": "user", "content": "ok"})
        return TactusResult(output="ok")

    agent._turn_without_streaming = MethodType(fake_turn, agent)

    agent._execute_turn({"message": "hello"})

    assert attempts["count"] == 2
    assert len(agent._history.get()) == 1
    assert agent._history.get()[0]["content"] == "ok"


def test_retry_config_retries_validation_and_truncates_history():
    attempts = {"count": 0}

    agent = DSPyAgentHandle(
        name="worker",
        system_prompt="test",
        model=None,
        module="Raw",
        retry={"attempts": 2, "delay_seconds": 0.0, "on": "infra_plus_validation"},
    )

    def fake_turn(self, opts, prompt_context):
        attempts["count"] += 1
        if attempts["count"] == 1:
            self._history.add({"role": "user", "content": "temp"})
            raise ValueError("bad response")
        self._history.add({"role": "user", "content": "ok"})
        return TactusResult(output="ok")

    agent._turn_without_streaming = MethodType(fake_turn, agent)

    agent._execute_turn({"message": "hello"})

    assert attempts["count"] == 2
    assert len(agent._history.get()) == 1
    assert agent._history.get()[0]["content"] == "ok"


def test_retry_config_infra_only_does_not_retry_value_error():
    attempts = {"count": 0}

    agent = DSPyAgentHandle(
        name="worker",
        system_prompt="test",
        model=None,
        module="Raw",
        retry={"attempts": 3, "delay_seconds": 0.0, "on": "infra_only"},
    )

    def fake_turn(self, opts, prompt_context):
        attempts["count"] += 1
        raise ValueError("validation failure")

    agent._turn_without_streaming = MethodType(fake_turn, agent)

    import pytest

    with pytest.raises(ValueError, match="validation failure"):
        agent._execute_turn({"message": "hello"})

    assert attempts["count"] == 1


def test_retry_config_validation_only_does_not_retry_runtime_error():
    attempts = {"count": 0}

    agent = DSPyAgentHandle(
        name="worker",
        system_prompt="test",
        model=None,
        module="Raw",
        retry={"attempts": 3, "delay_seconds": 0.0, "on": "validation_only"},
    )

    def fake_turn(self, opts, prompt_context):
        attempts["count"] += 1
        raise RuntimeError("infra-ish failure")

    agent._turn_without_streaming = MethodType(fake_turn, agent)

    import pytest

    with pytest.raises(RuntimeError, match="infra-ish failure"):
        agent._execute_turn({"message": "hello"})

    assert attempts["count"] == 1


def test_retry_config_overrides_legacy_response_retries():
    attempts = {"count": 0}

    agent = DSPyAgentHandle(
        name="worker",
        system_prompt="test",
        model=None,
        module="Raw",
        response={"retries": 5, "retry_delay": 0.0},
        retry={"attempts": 2, "delay_seconds": 0.0, "on": "infra_plus_validation"},
    )

    def fake_turn(self, opts, prompt_context):
        attempts["count"] += 1
        raise ValueError("boom")

    agent._turn_without_streaming = MethodType(fake_turn, agent)

    import pytest

    with pytest.raises(ValueError, match="boom"):
        agent._execute_turn({"message": "hello"})

    assert attempts["count"] == 2
