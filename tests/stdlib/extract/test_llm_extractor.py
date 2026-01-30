from types import SimpleNamespace

import pytest

from tactus.stdlib.extract.llm import LLMExtractor


class FakeAgent:
    def __init__(self, responses):
        self._responses = list(responses)

    def __call__(self, input_dict):
        return {"response": self._responses.pop(0)}

    def reset(self):
        return None


def test_llm_extractor_success():
    extractor = LLMExtractor(
        fields={"name": "string", "age": "number"},
        prompt="Extract",
        agent_factory=lambda cfg: FakeAgent(['{"name": "Ada", "age": 12}']),
    )
    result = extractor.extract("Ada is 12")
    assert result.fields["name"] == "Ada"
    assert result.fields["age"] == 12
    assert result.retry_count == 0


def test_llm_extractor_retry_then_success():
    extractor = LLMExtractor(
        fields={"name": "string"},
        prompt="Extract",
        agent_factory=lambda cfg: FakeAgent(["no json", '{"name": "Bob"}']),
        max_retries=1,
    )
    result = extractor.extract("Bob")
    assert result.fields["name"] == "Bob"
    assert result.retry_count == 1


def test_llm_extractor_parse_errors():
    extractor = LLMExtractor(
        fields={"flag": "boolean"},
        prompt="Extract",
        agent_factory=lambda cfg: FakeAgent(['{"flag": "maybe"}']),
    )
    parsed, errors = extractor._parse_response('{"flag": "maybe"}')
    assert errors
    assert parsed["flag"] is None


def test_llm_extractor_validate_field_types():
    extractor = LLMExtractor(
        fields={"value": "integer"},
        prompt="Extract",
        agent_factory=lambda cfg: FakeAgent(['{"value": 1}']),
    )
    value, error = extractor._validate_field("value", "2", "integer")
    assert value == 2
    assert error is None


def test_llm_extractor_builds_system_prompt_and_model_config():
    configs = {}

    def agent_factory(config):
        configs.update(config)
        return lambda _input: {"response": '{"name": "Ada"}'}

    extractor = LLMExtractor(
        fields={"name": "string"},
        prompt="Extract name",
        agent_factory=agent_factory,
        model="test-model",
    )

    assert "FIELDS TO EXTRACT" in extractor._system_prompt
    assert configs["model"] == "test-model"


def test_llm_extractor_requires_agent_factory():
    with pytest.raises(RuntimeError):
        LLMExtractor(fields={"name": "string"}, prompt="Extract", agent_factory=None)


def test_llm_extractor_call_agent_result_shapes():
    extractor = LLMExtractor(
        fields={"name": "string"},
        prompt="Extract",
        agent_factory=lambda _config: lambda _input: {"response": '{"name": "Ada"}'},
    )

    assert extractor._call_agent("msg")["response"] == '{"name": "Ada"}'

    extractor._agent = lambda _input: SimpleNamespace(message="hi")
    assert extractor._call_agent("msg")["response"] == "hi"

    extractor._agent = lambda _input: SimpleNamespace(response="yo")
    assert extractor._call_agent("msg")["response"] == "yo"

    extractor._agent = lambda _input: "plain"
    assert extractor._call_agent("msg")["response"] == "plain"

    class Result:
        def to_dict(self):
            return {"response": '{"name": "Ada"}'}

    extractor._agent = lambda _input: Result()
    assert extractor._call_agent("msg")["response"] == '{"name": "Ada"}'


def test_llm_extractor_parse_response_missing_json():
    extractor = LLMExtractor(
        fields={"name": "string"},
        prompt="Extract",
        agent_factory=lambda _config: lambda _input: {},
    )

    parsed, errors = extractor._parse_response("no json here")
    assert parsed == {}
    assert errors == ["No JSON object found in response"]


def test_llm_extractor_parse_response_empty():
    extractor = LLMExtractor(
        fields={"name": "string"},
        prompt="Extract",
        agent_factory=lambda _config: lambda _input: {},
    )

    parsed, errors = extractor._parse_response("")
    assert parsed == {}
    assert errors == ["Empty response"]


def test_llm_extractor_parse_response_nested_json():
    extractor = LLMExtractor(
        fields={"flag": "boolean"},
        prompt="Extract",
        agent_factory=lambda _config: lambda _input: {},
        strict=False,
    )

    parsed, errors = extractor._parse_response('prefix {"flag": true, "extra": {"x": 1}} suffix')
    assert parsed["flag"] is None
    assert errors == []


def test_llm_extractor_parse_response_invalid_json():
    extractor = LLMExtractor(
        fields={"name": "string"},
        prompt="Extract",
        agent_factory=lambda _config: lambda _input: {},
    )

    parsed, errors = extractor._parse_response('{"name": }')
    assert parsed == {}
    assert errors


def test_llm_extractor_parse_response_missing_fields_non_strict():
    extractor = LLMExtractor(
        fields={"name": "string", "age": "number"},
        prompt="Extract",
        agent_factory=lambda _config: lambda _input: {},
        strict=False,
    )

    parsed, errors = extractor._parse_response('{"name": "Ada"}')
    assert errors == []
    assert parsed["age"] is None


def test_llm_extractor_parse_response_missing_fields_strict():
    extractor = LLMExtractor(
        fields={"name": "string", "age": "number"},
        prompt="Extract",
        agent_factory=lambda _config: lambda _input: {},
    )

    parsed, errors = extractor._parse_response('{"name": "Ada"}')
    assert parsed["age"] is None
    assert errors == ["Missing required field: age"]


def test_llm_extractor_validate_field_variants():
    extractor = LLMExtractor(
        fields={"value": "string"},
        prompt="Extract",
        agent_factory=lambda _config: lambda _input: {},
    )

    value, error = extractor._validate_field("value", "yes", "boolean")
    assert value is True
    assert error is None

    value, error = extractor._validate_field("value", "no", "boolean")
    assert value is False
    assert error is None

    value, error = extractor._validate_field("value", "bad", "boolean")
    assert value is None
    assert error

    value, error = extractor._validate_field("value", 1, "boolean")
    assert value is None
    assert error

    value, error = extractor._validate_field("value", True, "boolean")
    assert value is True
    assert error is None

    value, error = extractor._validate_field("value", "nope", "number")
    assert value is None
    assert error

    value, error = extractor._validate_field("value", None, "integer")
    assert value is None
    assert error is None

    value, error = extractor._validate_field("value", 5, "integer")
    assert value == 5
    assert error is None

    value, error = extractor._validate_field("value", "nope", "integer")
    assert value is None
    assert error

    value, error = extractor._validate_field("value", True, "integer")
    assert value == 1
    assert error is None

    value, error = extractor._validate_field("value", ["a"], "list")
    assert value == ["a"]
    assert error is None

    value, error = extractor._validate_field("value", "nope", "list")
    assert value is None
    assert error

    value, error = extractor._validate_field("value", {"a": 1}, "dict")
    assert value == {"a": 1}
    assert error is None

    value, error = extractor._validate_field("value", "nope", "dict")
    assert value is None
    assert error

    value, error = extractor._validate_field("value", 5, "unknown")
    assert value == 5
    assert error is None


def test_llm_extractor_build_retry_feedback_includes_errors():
    extractor = LLMExtractor(
        fields={"name": "string"},
        prompt="Extract",
        agent_factory=lambda _config: lambda _input: {},
    )

    feedback = extractor._build_retry_feedback("oops", ["missing name"])
    assert "missing name" in feedback
    assert '"name"' in feedback


def test_llm_extractor_extract_handles_agent_exception():
    class Agent:
        def __call__(self, _input):
            raise RuntimeError("boom")

        def reset(self):
            pass

    extractor = LLMExtractor(
        fields={"name": "string"},
        prompt="Extract",
        agent_factory=lambda _config: Agent(),
    )

    result = extractor.extract("Ada")

    assert result.error == "boom"
    assert result.retry_count == 0


def test_llm_extractor_extract_exhausts_retries():
    class Agent:
        def __init__(self):
            self.calls = 0

        def __call__(self, _input):
            self.calls += 1
            return {"response": "not json"}

        def reset(self):
            pass

    agent = Agent()
    extractor = LLMExtractor(
        fields={"name": "string"},
        prompt="Extract",
        agent_factory=lambda _config: agent,
        max_retries=1,
    )

    result = extractor.extract("Ada")

    assert result.error
    assert result.retry_count == 1
    assert agent.calls == 2


def test_llm_extractor_extract_without_agent_reset():
    class Agent:
        def __call__(self, _input):
            return {"response": '{"name": "Ada"}'}

    extractor = LLMExtractor(
        fields={"name": "string"},
        prompt="Extract",
        agent_factory=lambda _config: Agent(),
    )

    result = extractor.extract("Ada")

    assert result.fields["name"] == "Ada"


def test_llm_extractor_reset_and_repr():
    reset_calls = {"count": 0}

    class Agent:
        def __call__(self, _input):
            return {"response": "{}"}

        def reset(self):
            reset_calls["count"] += 1

    extractor = LLMExtractor(
        fields={"name": "string"},
        prompt="Extract",
        agent_factory=lambda _config: Agent(),
    )

    extractor.reset()
    assert reset_calls["count"] == 1
    assert "LLMExtractor(fields=[" in repr(extractor)


def test_llm_extractor_reset_handles_agents_without_reset():
    class Agent:
        def __call__(self, _input):
            return {"response": "{}"}

    extractor = LLMExtractor(
        fields={"name": "string"},
        prompt="Extract",
        agent_factory=lambda _config: Agent(),
    )

    extractor.reset()
