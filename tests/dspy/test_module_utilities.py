from types import SimpleNamespace

import pytest
import dspy

from tactus.dspy.module import RawModule, TactusModule, create_module


def test_raw_module_parses_output_fields():
    module = RawModule(signature="a, b -> x, y")
    assert module.output_fields == ["x", "y"]


def test_raw_module_parses_default_output_fields():
    module = RawModule(signature="user_message")
    assert module.output_fields == ["response"]


def test_tactus_module_derives_schemas():
    module = TactusModule(name="mod", signature="question -> answer", strategy="predict")
    assert "question" in module.input_schema
    assert "answer" in module.output_schema


def test_create_module_requires_signature():
    with pytest.raises(ValueError, match="requires a 'signature'"):
        create_module("mod", {})


def test_create_module_rejects_unknown_strategy():
    with pytest.raises(ValueError, match="Unknown strategy"):
        create_module("mod", {"signature": "q -> a", "strategy": "weird"})


def test_lua_callable_module_returns_mock_response():
    registry = SimpleNamespace(mocks={"mod": {"returns": {"answer": "ok"}}})

    class MockManager:
        def get_mock_response(self, name, inputs):
            return {"answer": "ok"}

    lua_module = create_module(
        "mod",
        {"signature": "q -> a", "strategy": "predict"},
        registry=registry,
        mock_manager=MockManager(),
    )

    assert lua_module({"q": "hi"}) == {"answer": "ok"}


def test_raw_module_raises_without_lm(monkeypatch):
    module = RawModule()
    monkeypatch.setattr(dspy.settings, "lm", None)

    with pytest.raises(RuntimeError, match="No LM configured"):
        module(system_prompt="", history="", user_message="hi")


def test_raw_module_builds_messages_from_history(monkeypatch):
    module = RawModule()
    recorded = {}

    class FakeLM:
        kwargs = {}

        def __call__(self, messages, **kwargs):
            recorded["messages"] = messages
            recorded["kwargs"] = kwargs
            return ["ok"]

    monkeypatch.setattr(dspy.settings, "lm", FakeLM())

    history = "User: hi\nAssistant: hello"
    result = module(system_prompt="system", history=history, user_message="next")

    assert result.response == "ok"
    roles = [msg["role"] for msg in recorded["messages"]]
    assert roles == ["system", "user", "assistant", "user"]


def test_raw_module_handles_scalar_lm_response(monkeypatch):
    module = RawModule()

    class FakeLM:
        kwargs = {}

        def __call__(self, messages, **kwargs):
            return "ok"

    monkeypatch.setattr(dspy.settings, "lm", FakeLM())

    result = module(system_prompt="", history="", user_message="hi")

    assert result.response == "ok"


def test_raw_module_includes_available_tools(monkeypatch):
    module = RawModule(
        signature="system_prompt, history, user_message, available_tools -> response"
    )

    class FakeLM:
        kwargs = {}

        def __call__(self, messages, **kwargs):
            return [messages[-1]["content"]]

    monkeypatch.setattr(dspy.settings, "lm", FakeLM())

    result = module(
        system_prompt="",
        history="",
        user_message="hello",
        available_tools="tool_a",
    )

    assert "Available tools" in result.response


def test_raw_module_extracts_tool_calls(monkeypatch):
    module = RawModule(
        signature="system_prompt, history, user_message, available_tools -> response, tool_calls"
    )

    tool_calls = [{"function": {"name": "do", "arguments": '{"x": 1}'}}]

    class FakeLM:
        kwargs = {}

        def __call__(self, messages, **kwargs):
            return [{"text": "ok", "tool_calls": tool_calls}]

    monkeypatch.setattr(dspy.settings, "lm", FakeLM())

    result = module(system_prompt="", history="", user_message="hi", available_tools="x")

    assert result.response == "ok"
    assert result.tool_calls is not None


def test_raw_module_passes_tools_and_tool_choice(monkeypatch):
    module = RawModule(
        signature="system_prompt, history, user_message, available_tools -> response"
    )
    recorded = {}

    class FakeTool:
        def format_as_litellm_function_call(self):
            return {"name": "tool"}

    class FakeLM:
        kwargs = {"tool_choice": "auto"}

        def __call__(self, messages, **kwargs):
            recorded["kwargs"] = kwargs
            return ["ok"]

    monkeypatch.setattr(dspy.settings, "lm", FakeLM())

    module(system_prompt="", history="", user_message="hi", available_tools="x", tools=[FakeTool()])

    assert recorded["kwargs"]["tools"] == [{"name": "tool"}]
    assert recorded["kwargs"]["tool_choice"] == "auto"


def test_raw_module_ignores_tools_without_formatter(monkeypatch):
    module = RawModule(signature="system_prompt, history, user_message -> response")
    recorded = {}

    class NoFormatTool:
        pass

    class FakeLM:
        kwargs = {}

        def __call__(self, messages, **kwargs):
            recorded["kwargs"] = kwargs
            return ["ok"]

    monkeypatch.setattr(dspy.settings, "lm", FakeLM())

    module(system_prompt="", history="", user_message="hi", tools=[NoFormatTool()])

    assert "tools" not in recorded["kwargs"]


def test_raw_module_respects_explicit_tool_choice(monkeypatch):
    module = RawModule(
        signature="system_prompt, history, user_message, available_tools -> response"
    )
    recorded = {}

    class FakeTool:
        def format_as_litellm_function_call(self):
            return {"name": "tool"}

    class FakeLM:
        kwargs = {"tool_choice": "auto"}

        def __call__(self, messages, **kwargs):
            recorded["kwargs"] = kwargs
            return ["ok"]

    monkeypatch.setattr(dspy.settings, "lm", FakeLM())

    module(
        system_prompt="",
        history="",
        user_message="hi",
        available_tools="x",
        tools=[FakeTool()],
        tool_choice="required",
    )

    assert recorded["kwargs"]["tool_choice"] == "required"


def test_raw_module_sanitizes_tool_messages(monkeypatch):
    module = RawModule()
    recorded = {}

    tool_call = SimpleNamespace(
        id="id",
        type="function",
        function=SimpleNamespace(name="tool", arguments="{}"),
    )

    history = SimpleNamespace(
        messages=[
            {
                "role": "tool",
                "content": "result",
                "tool_call_id": "id",
                "name": "tool",
                "tool_calls": tool_call,
            }
        ]
    )

    class FakeLM:
        kwargs = {}

        def __call__(self, messages, **kwargs):
            recorded["messages"] = messages
            return ["ok"]

    monkeypatch.setattr(dspy.settings, "lm", FakeLM())

    module(system_prompt="", history=history, user_message="next")

    assert recorded["messages"][0]["tool_call_id"] == "id"
    assert recorded["messages"][0]["tool_calls"][0]["function"]["name"] == "tool"


def test_raw_module_sanitizes_tool_calls_list_objects(monkeypatch):
    module = RawModule()
    recorded = {}

    tool_call = SimpleNamespace(
        id="id",
        type="function",
        function=SimpleNamespace(name="tool", arguments="{}"),
    )

    history = SimpleNamespace(
        messages=[{"role": "assistant", "content": "hi", "tool_calls": [tool_call]}]
    )

    class FakeLM:
        kwargs = {}

        def __call__(self, messages, **kwargs):
            recorded["messages"] = messages
            return ["ok"]

    monkeypatch.setattr(dspy.settings, "lm", FakeLM())

    module(system_prompt="", history=history, user_message="next")

    assert recorded["messages"][0]["tool_calls"][0]["function"]["name"] == "tool"


def test_raw_module_preserves_dict_tool_calls(monkeypatch):
    module = RawModule()
    recorded = {}

    history = SimpleNamespace(
        messages=[
            {
                "role": "assistant",
                "content": "hi",
                "tool_calls": [{"id": "1", "type": "function", "function": {"name": "tool"}}],
            }
        ]
    )

    class FakeLM:
        kwargs = {}

        def __call__(self, messages, **kwargs):
            recorded["messages"] = messages
            return ["ok"]

    monkeypatch.setattr(dspy.settings, "lm", FakeLM())

    module(system_prompt="", history=history, user_message="next")

    assert recorded["messages"][0]["tool_calls"][0]["function"]["name"] == "tool"


def test_raw_module_tool_message_without_metadata(monkeypatch):
    module = RawModule()
    recorded = {}

    history = SimpleNamespace(messages=[{"role": "tool", "content": "result"}])

    class FakeLM:
        kwargs = {}

        def __call__(self, messages, **kwargs):
            recorded["messages"] = messages
            return ["ok"]

    monkeypatch.setattr(dspy.settings, "lm", FakeLM())

    module(system_prompt="", history=history, user_message="next")

    assert "tool_call_id" not in recorded["messages"][0]
    assert "name" not in recorded["messages"][0]


def test_raw_module_tool_calls_empty_list(monkeypatch):
    module = RawModule()
    recorded = {}

    history = SimpleNamespace(messages=[{"role": "assistant", "content": "hi", "tool_calls": []}])

    class FakeLM:
        kwargs = {}

        def __call__(self, messages, **kwargs):
            recorded["messages"] = messages
            return ["ok"]

    monkeypatch.setattr(dspy.settings, "lm", FakeLM())

    module(system_prompt="", history=history, user_message="next")

    assert "tool_calls" not in recorded["messages"][0]


def test_raw_module_skips_unknown_history_lines(monkeypatch):
    module = RawModule()
    recorded = {}

    class FakeLM:
        kwargs = {}

        def __call__(self, messages, **kwargs):
            recorded["messages"] = messages
            return ["ok"]

    monkeypatch.setattr(dspy.settings, "lm", FakeLM())

    history = "System: ignore\nUser: hi\nAssistant: ok"
    module(system_prompt="", history=history, user_message="")

    roles = [msg["role"] for msg in recorded["messages"]]
    assert roles == ["user", "assistant"]


def test_raw_module_parses_history_string(monkeypatch):
    module = RawModule()
    recorded = {}

    class FakeLM:
        kwargs = {}

        def __call__(self, messages, **kwargs):
            recorded["messages"] = messages
            return ["ok"]

    monkeypatch.setattr(dspy.settings, "lm", FakeLM())

    module(system_prompt="", history="User: hi", user_message=None)

    assert recorded["messages"][0]["role"] == "user"


def test_raw_module_ignores_blank_history(monkeypatch):
    module = RawModule()
    recorded = {}

    class FakeLM:
        kwargs = {}

        def __call__(self, messages, **kwargs):
            recorded["messages"] = messages
            return ["ok"]

    monkeypatch.setattr(dspy.settings, "lm", FakeLM())

    module(system_prompt="", history="   ", user_message="hi")

    assert recorded["messages"][0]["role"] == "user"


def test_raw_module_tool_calls_empty_when_missing(monkeypatch):
    module = RawModule(
        signature="system_prompt, history, user_message, available_tools -> response, tool_calls"
    )

    class FakeLM:
        kwargs = {}

        def __call__(self, messages, **kwargs):
            return [{"text": "ok"}]

    monkeypatch.setattr(dspy.settings, "lm", FakeLM())

    result = module(system_prompt="", history="", user_message="hi", available_tools="")

    assert result.tool_calls is not None


def test_tactus_module_uses_signature_schemas():
    signature = SimpleNamespace(
        input_fields={"q": SimpleNamespace(description="Question")},
        output_fields={"a": SimpleNamespace(description=None)},
    )
    module = TactusModule(name="mod", signature=signature, strategy="predict")

    assert module.input_schema["q"]["description"] == "Question"
    assert module.output_schema["a"]["description"] == "a"


def test_tactus_module_raw_strategy_uses_string_signature(monkeypatch):
    monkeypatch.setattr("tactus.dspy.module.create_signature", lambda signature: signature)

    module = TactusModule(
        name="mod",
        signature="question -> answer",
        strategy="raw",
    )

    assert isinstance(module.module, RawModule)


def test_lua_callable_module_passes_through_without_mocks(monkeypatch):
    module = TactusModule(name="mod", signature="question -> answer", strategy="predict")
    lua_module = create_module(
        "mod", {"signature": "question -> answer"}, registry=None, mock_manager=None
    )

    class FakePredict:
        def __call__(self, **kwargs):
            return dspy.Prediction(answer="ok")

    monkeypatch.setattr(module, "module", FakePredict())
    lua_module.module = module

    result = lua_module({"question": "hi"})
    assert result.answer == "ok"


def test_lua_callable_module_passes_through_when_mock_missing(monkeypatch):
    registry = SimpleNamespace(mocks={})

    class DummyMockManager:
        def get_mock_response(self, name, inputs):
            return {"answer": "ok"}

    module = TactusModule(name="mod", signature="question -> answer", strategy="predict")

    class FakePredict:
        def __call__(self, **kwargs):
            return dspy.Prediction(answer="ok")

    module.module = FakePredict()
    lua_module = create_module(
        "mod",
        {"signature": "question -> answer"},
        registry=registry,
        mock_manager=DummyMockManager(),
    )
    lua_module.module = module

    result = lua_module({"question": "hi"})
    assert result.answer == "ok"


def test_lua_callable_module_returns_none_for_missing_mock():
    registry = SimpleNamespace(mocks={})

    class DummyMockManager:
        def get_mock_response(self, name, inputs):
            return {"answer": "ok"}

    lua_module = create_module(
        "mod",
        {"signature": "question -> answer"},
        registry=registry,
        mock_manager=DummyMockManager(),
    )

    assert lua_module._get_mock_response({"question": "hi"}) is None


def test_lua_callable_module_mock_error_propagates():
    registry = SimpleNamespace(mocks={"mod": {"returns": {"answer": "ok"}}})

    class ExplodingMockManager:
        def get_mock_response(self, name, inputs):
            raise RuntimeError("boom")

    lua_module = create_module(
        "mod",
        {"signature": "question -> answer"},
        registry=registry,
        mock_manager=ExplodingMockManager(),
    )

    with pytest.raises(RuntimeError, match="boom"):
        lua_module._get_mock_response({"question": "hi"})


def test_lua_callable_module_properties():
    module = TactusModule(name="mod", signature="question -> answer", strategy="predict")
    lua_module = create_module("mod", {"signature": "question -> answer"})
    lua_module.module = module

    assert lua_module.name == "mod"
    assert lua_module.strategy == "predict"
    assert "question" in lua_module.input_schema
    assert "answer" in lua_module.output_schema
