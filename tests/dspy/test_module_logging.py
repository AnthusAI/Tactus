import os

import dspy

from tactus.dspy.module import RawModule


def test_raw_module_logs_non_serializable_payload(monkeypatch):
    class DummyLM:
        def __call__(self, *args, **kwargs):
            return ["ok"]

    original_lm = dspy.settings.lm
    dspy.settings.lm = DummyLM()
    monkeypatch.setenv("TACTUS_TRACE_LLM_MESSAGES", "1")

    class History:
        messages = [{"role": "user", "content": {"bad": {1, 2}}}]

    module = RawModule()
    result = module(system_prompt="", history=History(), user_message="hi")
    assert result.response == "ok"

    dspy.settings.lm = original_lm
    os.environ.pop("TACTUS_TRACE_LLM_MESSAGES", None)
