from types import SimpleNamespace

from tactus.dspy.agent import DSPyAgentHandle
from tactus.protocols.cost import CostStats, UsageStats


class _DummyToolPrimitive:
    def __init__(self):
        self.calls = []

    def record_call(self, tool_name, args, result, agent_name=None):
        self.calls.append((tool_name, args, result, agent_name))


def _prediction(response="", tool_calls=None):
    calls = tool_calls or []
    payload = SimpleNamespace(tool_calls=calls) if calls else None
    return SimpleNamespace(response=response, tool_calls=payload)


def _make_agent(monkeypatch, module_fn):
    monkeypatch.setattr(
        DSPyAgentHandle,
        "_build_module",
        lambda self: SimpleNamespace(module=module_fn),
    )
    agent = DSPyAgentHandle(name="agent", model=None)
    monkeypatch.setattr(agent, "_extract_last_call_stats", lambda: (UsageStats(), CostStats()))
    monkeypatch.setattr(agent, "_emit_cost_event", lambda: None)
    monkeypatch.setattr(
        agent,
        "_wrap_as_result",
        lambda wrapped, usage, cost: SimpleNamespace(
            output=getattr(wrapped, "response", ""), value=wrapped, usage=usage, cost_stats=cost
        ),
    )
    return agent


def test_non_streaming_tool_chain_until_final_answer(monkeypatch):
    calls = []
    results = [
        _prediction(tool_calls=[{"id": "c1", "name": "agent_tool_a", "args": {"x": 1}}]),
        _prediction(tool_calls=[{"id": "c2", "name": "agent_tool_b", "args": {"y": 2}}]),
        _prediction(response="Final answer"),
    ]

    def module_fn(**kwargs):
        calls.append(kwargs)
        return results[len(calls) - 1]

    agent = _make_agent(monkeypatch, module_fn)
    agent._tool_primitive = _DummyToolPrimitive()
    exec_calls = []
    monkeypatch.setattr(
        agent,
        "_execute_tool",
        lambda name, args: exec_calls.append((name, args)) or {"ok": name},
    )

    result = agent._turn_without_streaming(
        {"message": "run tools"},
        {"system_prompt": "s", "history": agent._history.to_dspy(), "user_message": "run tools"},
    )

    assert len(calls) == 3
    assert [name for name, _ in exec_calls] == ["agent_tool_a", "agent_tool_b"]
    assert result.value.response == "Final answer"
    assert [c[0] for c in agent._tool_primitive.calls] == ["tool_a", "tool_b"]


def test_non_streaming_single_tool_then_final(monkeypatch):
    call_count = 0

    def module_fn(**_kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _prediction(tool_calls=[{"id": "c1", "name": "agent_tool_a", "args": {}}])
        return _prediction(response="Done")

    agent = _make_agent(monkeypatch, module_fn)
    monkeypatch.setattr(agent, "_execute_tool", lambda _name, _args: {"ok": True})

    result = agent._turn_without_streaming(
        {"message": "do it"},
        {"system_prompt": "s", "history": agent._history.to_dspy(), "user_message": "do it"},
    )

    assert call_count == 2
    assert result.value.response == "Done"


def test_non_streaming_without_tools_unchanged(monkeypatch):
    call_count = 0

    def module_fn(**_kwargs):
        nonlocal call_count
        call_count += 1
        return _prediction(response="Plain answer")

    agent = _make_agent(monkeypatch, module_fn)
    result = agent._turn_without_streaming(
        {"message": "hello"},
        {"system_prompt": "s", "history": agent._history.to_dspy(), "user_message": "hello"},
    )

    assert call_count == 1
    assert result.value.response == "Plain answer"


def test_non_streaming_forces_one_synthesis_when_terminal_text_missing(monkeypatch):
    seen_user_messages = []
    call_count = 0

    def module_fn(**kwargs):
        nonlocal call_count
        call_count += 1
        seen_user_messages.append(kwargs.get("user_message"))
        if call_count == 1:
            return _prediction(tool_calls=[{"id": "c1", "name": "agent_tool_a", "args": {}}])
        if call_count == 2:
            return _prediction(response="")
        return _prediction(response="Synthesis answer")

    agent = _make_agent(monkeypatch, module_fn)
    monkeypatch.setattr(agent, "_execute_tool", lambda _name, _args: {"ok": True})

    result = agent._turn_without_streaming(
        {"message": "help"},
        {"system_prompt": "s", "history": agent._history.to_dspy(), "user_message": "help"},
    )

    assert call_count == 3
    assert seen_user_messages[0] == "help"
    assert seen_user_messages[1] == ""
    assert seen_user_messages[2].startswith("Provide the final user-facing answer now")
    assert result.value.response == "Synthesis answer"


class _DummyLogHandler:
    supports_streaming = True

    def __init__(self):
        self.events = []

    def log(self, event):
        self.events.append(event)


def test_streaming_tool_chain_until_final_answer(monkeypatch):
    calls = []
    results = [
        _prediction(tool_calls=[{"id": "c1", "name": "agent_tool_a", "args": {"x": 1}}]),
        _prediction(response="Final streamed answer"),
    ]

    def module_fn(**kwargs):
        calls.append(kwargs)
        return results[len(calls) - 1]

    agent = _make_agent(monkeypatch, module_fn)
    agent.log_handler = _DummyLogHandler()
    monkeypatch.setattr(agent, "_execute_tool", lambda _name, _args: {"ok": True})

    def fake_streamify(fn):
        async def _wrapped(**kwargs):
            yield fn(**kwargs)

        return _wrapped

    monkeypatch.setattr("dspy.streamify", fake_streamify)

    result = agent._turn_with_streaming(
        {"message": "stream tools"},
        {"system_prompt": "s", "history": agent._history.to_dspy(), "user_message": "stream tools"},
    )

    assert len(calls) == 2
    assert result.value.response == "Final streamed answer"


def test_streaming_forces_one_synthesis_when_terminal_text_missing(monkeypatch):
    seen_user_messages = []
    call_count = 0

    def module_fn(**kwargs):
        nonlocal call_count
        call_count += 1
        seen_user_messages.append(kwargs.get("user_message"))
        if call_count == 1:
            return _prediction(tool_calls=[{"id": "c1", "name": "agent_tool_a", "args": {}}])
        if call_count == 2:
            return _prediction(response="")
        return _prediction(response="Synth final")

    agent = _make_agent(monkeypatch, module_fn)
    agent.log_handler = _DummyLogHandler()
    monkeypatch.setattr(agent, "_execute_tool", lambda _name, _args: {"ok": True})

    def fake_streamify(fn):
        async def _wrapped(**kwargs):
            yield fn(**kwargs)

        return _wrapped

    monkeypatch.setattr("dspy.streamify", fake_streamify)

    result = agent._turn_with_streaming(
        {"message": "stream help"},
        {"system_prompt": "s", "history": agent._history.to_dspy(), "user_message": "stream help"},
    )

    assert call_count >= 3
    assert seen_user_messages[-1].startswith("Provide the final user-facing answer now")
    assert result.value.response == "Synth final"
