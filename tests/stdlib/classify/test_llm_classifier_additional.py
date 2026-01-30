import pytest

from tactus.stdlib.classify.llm import LLMClassifier


def test_create_agent_requires_factory():
    with pytest.raises(RuntimeError):
        LLMClassifier(classes=["Yes"], prompt="p", agent_factory=None)


def test_create_agent_includes_name_and_model():
    captured = {}

    def factory(config):
        captured.update(config)
        return config

    classifier = LLMClassifier(
        classes=["Yes"],
        prompt="p",
        agent_factory=factory,
        name="tester",
        model="gpt-test",
    )

    assert classifier._agent["name"] == "tester"
    assert classifier._agent["model"] == "gpt-test"


def test_call_agent_handles_result_shapes():
    classifier = LLMClassifier(
        classes=["Yes"],
        prompt="p",
        agent_factory=lambda _config: (lambda _input: {"response": "Yes"}),
    )

    class ResultWithDict:
        def to_dict(self):
            return {"response": "Yes"}

    class ResultWithMessage:
        def __init__(self, message):
            self.message = message

    class ResultWithResponse:
        def __init__(self, response):
            self.response = response

    classifier._agent = lambda _input: ResultWithDict()
    assert classifier._call_agent("msg") == {"response": "Yes"}

    classifier._agent = lambda _input: ResultWithMessage("Yes")
    assert classifier._call_agent("msg") == {"response": "Yes"}

    classifier._agent = lambda _input: ResultWithResponse("Yes")
    assert classifier._call_agent("msg") == {"response": "Yes"}

    classifier._agent = lambda _input: {"response": "Yes"}
    assert classifier._call_agent("msg") == {"response": "Yes"}

    classifier._agent = lambda _input: "Yes"
    assert classifier._call_agent("msg") == {"response": "Yes"}


def test_parse_response_handles_partial_match_rejection():
    classifier = LLMClassifier(
        classes=["cat", "catdog"],
        prompt="p",
        agent_factory=lambda _config: (lambda _input: {"response": "catdog"}),
    )
    parsed = classifier._parse_response("I think cat")
    assert parsed["value"] == "I think cat"


def test_parse_response_handles_token_match():
    classifier = LLMClassifier(
        classes=["Yes", "No"],
        prompt="p",
        agent_factory=lambda _config: (lambda _input: {"response": "Yes"}),
    )
    parsed = classifier._parse_response("Maybe Yes indeed")
    assert parsed["value"] == "Yes"


def test_parse_response_handles_empty():
    classifier = LLMClassifier(
        classes=["Yes"],
        prompt="p",
        agent_factory=lambda _config: (lambda _input: {"response": "Yes"}),
    )
    parsed = classifier._parse_response("")
    assert parsed["value"] is None


def test_parse_response_handles_whitespace():
    classifier = LLMClassifier(
        classes=["Yes"],
        prompt="p",
        agent_factory=lambda _config: (lambda _input: {"response": "Yes"}),
    )
    parsed = classifier._parse_response("   \n")
    assert parsed["value"] is None


def test_classify_returns_error_when_agent_call_fails():
    classifier = LLMClassifier(
        classes=["Yes"],
        prompt="p",
        agent_factory=lambda _config: (lambda _input: {"response": "Yes"}),
    )

    def boom(_message):
        raise RuntimeError("nope")

    classifier._call_agent = boom
    result = classifier.classify("text")
    assert result.value == "ERROR"
    assert result.error == "nope"


def test_reset_calls_agent_reset():
    called = {"reset": False}

    class Agent:
        def reset(self):
            called["reset"] = True

        def __call__(self, _input):
            return {"response": "Yes"}

    classifier = LLMClassifier(
        classes=["Yes"],
        prompt="p",
        agent_factory=lambda _config: Agent(),
    )

    classifier.reset()
    assert called["reset"] is True


def test_reset_noop_when_agent_has_no_reset():
    classifier = LLMClassifier(
        classes=["Yes"],
        prompt="p",
        agent_factory=lambda _config: (lambda _input: {"response": "Yes"}),
    )
    classifier._agent = lambda _input: {"response": "Yes"}
    classifier.reset()


def test_repr_includes_counts():
    classifier = LLMClassifier(
        classes=["Yes"],
        prompt="p",
        agent_factory=lambda _config: (lambda _input: {"response": "Yes"}),
    )
    assert "LLMClassifier" in repr(classifier)
