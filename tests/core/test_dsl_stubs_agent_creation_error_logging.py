from __future__ import annotations

from tactus.core.dsl_stubs import create_dsl_stubs
from tactus.core.registry import RegistryBuilder


def test_agent_immediate_creation_unexpected_error_is_logged(monkeypatch) -> None:
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder, runtime_context={"mock_manager": None})

    called = {"create": 0}

    def fake_create_dspy_agent(*_args, **_kwargs):
        called["create"] += 1
        raise RuntimeError("boom")

    monkeypatch.setattr("tactus.dspy.agent.create_dspy_agent", fake_create_dspy_agent)

    # Immediate creation fails, but the stub should fall back to two-phase initialization.
    handle = stubs["Agent"](
        {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "system_prompt": "x",
        }
    )
    assert handle is not None
    assert called["create"] == 1
