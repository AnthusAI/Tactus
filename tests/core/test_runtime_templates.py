import string

from tactus.core.runtime import TactusRuntime


class DummyState:
    def all(self):
        return {"phase": "alpha"}


class DummyIterations:
    def current(self):
        return 3


class DummyStop:
    def requested(self):
        return True


def test_process_template_with_context_and_defaults():
    runtime = TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.config = {"input": {"topic": {"default": "testing"}}}
    runtime.state_primitive = DummyState()

    template = "Topic={input.topic}, Phase={state.phase}, User={params.name}"
    result = runtime._process_template(template, {"params": {"name": "Ada"}})

    assert result == "Topic=testing, Phase=alpha, User=Ada"


def test_process_template_with_object_attribute():
    runtime = TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.config = {}

    class Dummy:
        def __init__(self, name):
            self.name = name

    template = "User={user.name}"
    result = runtime._process_template(template, {"user": Dummy("Ada")})

    assert result == "User=Ada"


def test_process_template_key_error(monkeypatch):
    runtime = TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.config = {}

    def fail_format(self, _template, **_kwargs):
        raise KeyError("missing")

    monkeypatch.setattr(string.Formatter, "format", fail_format)

    template = "Hello {missing}"
    result = runtime._process_template(template, {})

    assert result == template


def test_process_template_generic_error(monkeypatch):
    runtime = TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.config = {}

    def fail_format(self, _template, **_kwargs):
        raise ValueError("boom")

    monkeypatch.setattr(string.Formatter, "format", fail_format)

    template = "Hello {name}"
    result = runtime._process_template(template, {"name": "Ada"})

    assert result == template


def test_format_output_schema_for_prompt():
    runtime = TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.config = {
        "output": {
            "score": {"type": "number", "required": True, "description": "a score"},
            "label": {"type": "string", "required": False},
        }
    }

    output = runtime._format_output_schema_for_prompt()

    assert "Expected Output Format" in output
    assert "**score**" in output
    assert "a score" in output
    assert "**label**" in output


def test_format_output_schema_for_prompt_empty():
    runtime = TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.config = {}

    assert runtime._format_output_schema_for_prompt() == ""


def test_state_iteration_and_stop_helpers():
    runtime = TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.state_primitive = DummyState()
    runtime.iterations_primitive = DummyIterations()
    runtime.stop_primitive = DummyStop()

    assert runtime.get_state() == {"phase": "alpha"}
    assert runtime.get_iteration_count() == 3
    assert runtime.is_stopped() is True


def test_state_iteration_and_stop_helpers_default():
    runtime = TactusRuntime(procedure_id="proc", hitl_handler=object())

    assert runtime.get_state() == {}
    assert runtime.get_iteration_count() == 0
    assert runtime.is_stopped() is False
