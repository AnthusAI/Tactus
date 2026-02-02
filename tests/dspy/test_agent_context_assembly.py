import pytest

from types import SimpleNamespace

from tactus.dspy.agent import DSPyAgentHandle


def test_agent_context_requires_registry():
    agent = DSPyAgentHandle(name="agent", context_name="support", model=None)
    with pytest.raises(RuntimeError, match="Context assembly requires a registry"):
        agent({"message": "hello"})


def test_agent_context_assembly_path(monkeypatch):
    class DummyAssembler:
        def __init__(self, *args, **kwargs):
            pass

        def assemble(self, **_kwargs):
            return SimpleNamespace(
                system_prompt="sys",
                history=[],
                user_message="hi",
            )

    monkeypatch.setattr("tactus.core.context_assembler.ContextAssembler", DummyAssembler)

    registry = SimpleNamespace(
        contexts={"support": object()}, retrievers=None, corpora=None, compactors=None
    )
    agent = DSPyAgentHandle(
        name="agent",
        context_name="support",
        model=None,
        registry=registry,
        system_prompt="sys",
        disable_streaming=True,
    )

    monkeypatch.setattr(
        agent, "_turn_without_streaming", lambda *_args, **_kwargs: {"response": "ok"}
    )
    result = agent({"message": "hello"})
    assert result["response"] == "ok"


def test_agent_context_assembly_without_user_message(monkeypatch):
    class DummyAssembler:
        def __init__(self, *args, **kwargs):
            pass

        def assemble(self, **_kwargs):
            return SimpleNamespace(
                system_prompt="sys",
                history=[],
                user_message="",
            )

    monkeypatch.setattr("tactus.core.context_assembler.ContextAssembler", DummyAssembler)

    registry = SimpleNamespace(
        contexts={"support": object()}, retrievers=None, corpora=None, compactors=None
    )
    agent = DSPyAgentHandle(
        name="agent",
        context_name="support",
        model=None,
        registry=registry,
        system_prompt="sys",
        disable_streaming=True,
    )

    monkeypatch.setattr(
        agent, "_turn_without_streaming", lambda *_args, **_kwargs: {"response": "ok"}
    )
    result = agent({})
    assert result["response"] == "ok"
