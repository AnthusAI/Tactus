"""Tests for the Classify primitive with mocked agents."""

import pytest
from types import SimpleNamespace
import sys

from tactus.stdlib.classify.primitive import ClassifyPrimitive, ClassifyHandle, ClassifierFactory
from tactus.stdlib.classify.llm import LLMClassifier
from tactus.stdlib.core.models import ClassifierResult


class MockAgentHandle:
    """Mock agent handle for testing."""

    def __init__(self, responses=None):
        self.responses = responses or ["Yes"]
        self.call_count = 0
        self.messages = []

    def __call__(self, input_dict):
        self.messages.append(input_dict.get("message", ""))
        response = self.responses[min(self.call_count, len(self.responses) - 1)]
        self.call_count += 1
        return {"response": response}

    def reset(self):
        """Reset conversation state."""
        pass


def create_mock_agent_factory(responses):
    """Create a mock agent factory that returns agents with predefined responses."""

    def factory(config):
        return MockAgentHandle(responses)

    return factory


class TestClassifyPrimitive:
    """Tests for ClassifyPrimitive."""

    def test_classify_requires_classes(self):
        """Classify should raise error if classes not provided."""
        factory = create_mock_agent_factory(["Yes"])
        primitive = ClassifyPrimitive(agent_factory=factory)

        with pytest.raises(ValueError, match="classes"):
            primitive({"prompt": "Test prompt"})

    def test_classify_requires_prompt(self):
        """Classify should raise error if prompt not provided."""
        factory = create_mock_agent_factory(["Yes"])
        primitive = ClassifyPrimitive(agent_factory=factory)

        with pytest.raises(ValueError, match="prompt"):
            primitive({"classes": ["Yes", "No"]})

    def test_one_shot_classification(self):
        """Classify with input should return result directly."""
        factory = create_mock_agent_factory(["Yes"])
        primitive = ClassifyPrimitive(agent_factory=factory)

        result = primitive(
            {"classes": ["Yes", "No"], "prompt": "Is this positive?", "input": "Great product!"}
        )

        assert isinstance(result, dict)
        assert result["value"] == "Yes"

    def test_reusable_classifier(self):
        """Classify without input should return ClassifyHandle."""
        factory = create_mock_agent_factory(["Yes"])
        primitive = ClassifyPrimitive(agent_factory=factory)

        result = primitive({"classes": ["Yes", "No"], "prompt": "Is this positive?"})

        assert isinstance(result, ClassifyHandle)

    def test_handle_can_be_called_multiple_times(self):
        """ClassifyHandle should be callable multiple times."""
        responses = ["Yes", "No"]
        factory = create_mock_agent_factory(responses)
        primitive = ClassifyPrimitive(agent_factory=factory)

        handle = primitive({"classes": ["Yes", "No"], "prompt": "Is this positive?"})

        result1 = handle("Great!")
        assert result1.value == "Yes"

        # Reset and test again
        handle._agent = MockAgentHandle(["No"])
        result2 = handle("Terrible!")
        assert result2.value == "No"


class TestClassifyHandle:
    """Tests for ClassifyHandle."""

    def test_binary_classification_yes(self):
        """Handle should correctly classify 'Yes' response."""
        mock_agent = MockAgentHandle(["Yes\nThe text is clearly positive."])

        classifier = LLMClassifier(
            classes=["Yes", "No"],
            prompt="Is this positive?",
            agent_factory=lambda c: mock_agent,
        )
        classifier._agent = mock_agent
        handle = ClassifyHandle(classifier=classifier)

        result = handle("Great product!")

        assert result.value == "Yes"
        assert result.explanation == "The text is clearly positive."
        assert result.retry_count == 0

    def test_binary_classification_no(self):
        """Handle should correctly classify 'No' response."""
        mock_agent = MockAgentHandle(["No\nThe text is negative."])

        classifier = LLMClassifier(
            classes=["Yes", "No"],
            prompt="Is this positive?",
            agent_factory=lambda c: mock_agent,
        )
        handle = ClassifyHandle(classifier=classifier)
        handle._agent = mock_agent

        result = handle("Terrible service!")

        assert result.value == "No"
        assert result.retry_count == 0

    def test_multi_class_classification(self):
        """Handle should work with multiple classes."""
        mock_agent = MockAgentHandle(["neutral\nThe text shows mixed feelings."])

        classifier = LLMClassifier(
            classes=["positive", "negative", "neutral"],
            prompt="What is the sentiment?",
            agent_factory=lambda c: mock_agent,
        )
        handle = ClassifyHandle(classifier=classifier)
        handle._agent = mock_agent

        result = handle("It was okay.")

        assert result.value == "neutral"

    def test_retry_on_invalid_response(self):
        """Handle should retry when response is not in valid classes."""
        mock_agent = MockAgentHandle(["Maybe", "Yes"])

        classifier = LLMClassifier(
            classes=["Yes", "No"],
            prompt="Is this positive?",
            agent_factory=lambda c: mock_agent,
        )
        handle = ClassifyHandle(classifier=classifier)
        handle._agent = mock_agent

        result = handle("Great!")

        assert result.value == "Yes"
        assert result.retry_count == 1

    def test_multiple_retries(self):
        """Handle should retry multiple times before success."""
        # Use responses that don't accidentally contain "Yes" or "No" as substrings
        # (e.g., "Unknown" contains "no" which would match "No")
        invalid_responses = ["Invalid", "Maybe", "Perhaps", "Yes"]

        classifier = LLMClassifier(
            classes=["Yes", "No"],
            prompt="Is this positive?",
            max_retries=5,
            agent_factory=lambda c: MockAgentHandle(invalid_responses),
        )
        handle = ClassifyHandle(classifier=classifier)
        # Replace with fresh mock agent to avoid count issues from __init__
        handle._agent = MockAgentHandle(invalid_responses)

        result = handle("Great!")

        assert result.value == "Yes"
        assert result.retry_count == 3

    def test_max_retries_exceeded(self):
        """Handle should return error when max retries exceeded."""
        mock_agent = MockAgentHandle(["Invalid", "Invalid", "Invalid", "Invalid"])

        classifier = LLMClassifier(
            classes=["Yes", "No"],
            prompt="Is this positive?",
            max_retries=2,
            agent_factory=lambda c: mock_agent,
        )
        handle = ClassifyHandle(classifier=classifier)
        handle._agent = mock_agent

        result = handle("Great!")

        assert result.value == "ERROR"
        assert result.error is not None
        assert "Max retries" in result.error or "retries" in result.error.lower()
        assert result.retry_count == 2

    def test_retry_feedback_includes_valid_classes(self):
        """Retry message should include valid classification options."""
        mock_agent = MockAgentHandle(["Maybe", "Yes"])

        classifier = LLMClassifier(
            classes=["Yes", "No"],
            prompt="Is this positive?",
            agent_factory=lambda c: mock_agent,
        )
        handle = ClassifyHandle(classifier=classifier)
        handle._agent = mock_agent

        handle("Great!")

        # Check that the second message includes feedback
        assert len(mock_agent.messages) >= 2
        retry_message = mock_agent.messages[1]
        assert "Yes" in retry_message
        assert "No" in retry_message


class TestConfidenceExtraction:
    """Tests for confidence extraction heuristics."""

    def test_high_confidence_definitely(self):
        """'definitely' should map to high confidence."""
        mock_agent = MockAgentHandle(["Yes. This definitely indicates agreement."])

        classifier = LLMClassifier(
            classes=["Yes", "No"],
            prompt="Test",
            agent_factory=lambda c: mock_agent,
        )
        handle = ClassifyHandle(classifier=classifier)
        handle._agent = mock_agent

        result = handle("Test input")

        assert result.confidence is not None
        assert result.confidence >= 0.9

    def test_high_confidence_clearly(self):
        """'clearly' should map to high confidence."""
        mock_agent = MockAgentHandle(["Yes. The text clearly shows approval."])

        classifier = LLMClassifier(
            classes=["Yes", "No"],
            prompt="Test",
            agent_factory=lambda c: mock_agent,
        )
        handle = ClassifyHandle(classifier=classifier)
        handle._agent = mock_agent

        result = handle("Test input")

        assert result.confidence is not None
        assert result.confidence >= 0.9

    def test_medium_confidence_likely(self):
        """'likely' should map to medium-high confidence."""
        mock_agent = MockAgentHandle(["Yes. This is likely agreement."])

        classifier = LLMClassifier(
            classes=["Yes", "No"],
            prompt="Test",
            agent_factory=lambda c: mock_agent,
        )
        handle = ClassifyHandle(classifier=classifier)
        handle._agent = mock_agent

        result = handle("Test input")

        assert result.confidence is not None
        assert 0.7 <= result.confidence <= 0.9

    def test_low_confidence_uncertain(self):
        """'uncertain' should map to low confidence."""
        mock_agent = MockAgentHandle(["Yes. Though I'm uncertain about this assessment."])

        classifier = LLMClassifier(
            classes=["Yes", "No"],
            prompt="Test",
            agent_factory=lambda c: mock_agent,
        )
        handle = ClassifyHandle(classifier=classifier)
        handle._agent = mock_agent

        result = handle("Test input")

        assert result.confidence is not None
        assert result.confidence <= 0.6

    def test_confidence_mode_none(self):
        """confidence_mode='none' should return null confidence."""
        mock_agent = MockAgentHandle(["Yes. Definitely!"])

        classifier = LLMClassifier(
            classes=["Yes", "No"],
            prompt="Test",
            confidence_mode="none",
            agent_factory=lambda c: mock_agent,
        )
        handle = ClassifyHandle(classifier=classifier)
        handle._agent = mock_agent

        result = handle("Test input")

        assert result.confidence is None


class TestResponseParsing:
    """Tests for response parsing logic."""

    def test_parse_first_line(self):
        """Classification should be extracted from first line."""
        mock_agent = MockAgentHandle(["Yes\nBecause of the greeting."])

        classifier = LLMClassifier(
            classes=["Yes", "No"],
            prompt="Test",
            agent_factory=lambda c: mock_agent,
        )
        handle = ClassifyHandle(classifier=classifier)
        handle._agent = mock_agent

        result = handle("Test input")

        assert result.value == "Yes"
        assert result.explanation == "Because of the greeting."

    def test_parse_with_markdown(self):
        """Should handle markdown formatting in response."""
        mock_agent = MockAgentHandle(["**Yes** - the text is positive"])

        classifier = LLMClassifier(
            classes=["Yes", "No"],
            prompt="Test",
            agent_factory=lambda c: mock_agent,
        )
        handle = ClassifyHandle(classifier=classifier)
        handle._agent = mock_agent

        result = handle("Test input")

        assert result.value == "Yes"

    def test_parse_with_quotes(self):
        """Should handle quoted classification."""
        mock_agent = MockAgentHandle(['"Yes" is my classification'])

        classifier = LLMClassifier(
            classes=["Yes", "No"],
            prompt="Test",
            agent_factory=lambda c: mock_agent,
        )
        handle = ClassifyHandle(classifier=classifier)
        handle._agent = mock_agent

        result = handle("Test input")

        assert result.value == "Yes"

    def test_parse_prefix_match(self):
        """Should match classification as prefix of response."""
        mock_agent = MockAgentHandle(["Yes, the text indicates approval"])

        classifier = LLMClassifier(
            classes=["Yes", "No"],
            prompt="Test",
            agent_factory=lambda c: mock_agent,
        )
        handle = ClassifyHandle(classifier=classifier)
        handle._agent = mock_agent

        result = handle("Test input")

        assert result.value == "Yes"

    def test_case_insensitive_matching(self):
        """Classification matching should be case insensitive."""
        mock_agent = MockAgentHandle(["YES"])

        classifier = LLMClassifier(
            classes=["Yes", "No"],
            prompt="Test",
            agent_factory=lambda c: mock_agent,
        )
        handle = ClassifyHandle(classifier=classifier)
        handle._agent = mock_agent

        result = handle("Test input")

        assert result.value == "Yes"  # Should normalize to the defined class


class TestClassifyResult:
    """Tests for ClassifierResult data class."""

    def test_to_dict(self):
        """ClassifierResult should convert to dict."""
        result = ClassifierResult(
            value="Yes",
            confidence=0.9,
            explanation="Test explanation",
            retry_count=1,
            raw_response="Yes\nTest explanation",
        )

        d = result.to_dict()

        assert d["value"] == "Yes"
        assert d["confidence"] == 0.9
        assert d["explanation"] == "Test explanation"
        assert d["retry_count"] == 1
        assert d["raw_response"] == "Yes\nTest explanation"
        assert d["error"] is None

    def test_error_result(self):
        """ClassifierResult should handle error state."""
        result = ClassifierResult(
            value="ERROR",
            error="Max retries exceeded",
            retry_count=3,
        )

        d = result.to_dict()

        assert d["value"] == "ERROR"
        assert d["error"] == "Max retries exceeded"
        assert d["retry_count"] == 3


class DummyClassifier:
    def __init__(self):
        self.classes = ["yes", "no"]
        self.target_classes = ["yes"]
        self.total_calls = 0
        self.total_retries = 2

    def classify(self, text):
        self.total_calls += 1
        return ClassifierResult(value="yes", confidence=0.5)

    def reset(self):
        self.total_calls = 0


def test_classify_handle_dict_input_and_repr():
    handle = ClassifyHandle(classifier=DummyClassifier())
    result = handle({"input": "yes"})
    assert result.value == "yes"
    assert "ClassifyHandle" in repr(handle)


def test_classify_handle_reset_and_counters():
    classifier = DummyClassifier()
    handle = ClassifyHandle(classifier=classifier)
    handle("yes")
    assert handle.total_calls == 1
    assert handle.total_retries == 2
    handle.reset()
    assert handle.total_calls == 0


def test_classify_fuzzy_requires_expected_or_classes():
    primitive = ClassifyPrimitive(agent_factory=create_mock_agent_factory(["Yes"]))
    with pytest.raises(ValueError, match="expected"):
        primitive({"method": "fuzzy"})


def test_classify_fuzzy_accepts_expected_without_prompt():
    primitive = ClassifyPrimitive(agent_factory=create_mock_agent_factory(["Yes"]))
    handle = primitive({"method": "fuzzy", "expected": "Yes"})
    assert isinstance(handle, ClassifyHandle)


def test_classify_lua_to_python_handles_import_error(monkeypatch):
    primitive = ClassifyPrimitive(agent_factory=create_mock_agent_factory(["Yes"]))
    monkeypatch.setitem(sys.modules, "lupa", SimpleNamespace())
    try:
        assert primitive._lua_to_python({"a": 1}) == {"a": 1}
    finally:
        sys.modules.pop("lupa", None)


def test_classify_to_lua_table_uses_converter():
    primitive = ClassifyPrimitive(agent_factory=create_mock_agent_factory(["Yes"]))
    primitive.lua_table_from = lambda value: {"wrapped": value}
    output = primitive._to_lua_table({"value": "Yes"})
    assert output == {"wrapped": {"value": "Yes"}}


def test_classify_to_lua_table_returns_non_dict_value():
    primitive = ClassifyPrimitive(agent_factory=create_mock_agent_factory(["Yes"]))
    assert primitive._to_lua_table(["a"]) == ["a"]


def test_classify_to_lua_table_returns_non_dict_with_converter():
    primitive = ClassifyPrimitive(agent_factory=create_mock_agent_factory(["Yes"]))
    primitive.lua_table_from = lambda value: {"wrapped": value}
    assert primitive._to_lua_table(["a"]) == ["a"]


def test_classify_lua_to_python_handles_none():
    primitive = ClassifyPrimitive(agent_factory=create_mock_agent_factory(["Yes"]))
    assert primitive._lua_to_python(None) is None


def test_classify_lua_to_python_converts_table(monkeypatch):
    class FakeLuaTable:
        def __init__(self, items):
            self._items = items

        def items(self):
            return self._items.items()

    fake_lupa = SimpleNamespace(
        lua_type=lambda value: "table" if isinstance(value, FakeLuaTable) else "string"
    )
    monkeypatch.setitem(sys.modules, "lupa", fake_lupa)
    try:
        primitive = ClassifyPrimitive(agent_factory=create_mock_agent_factory(["Yes"]))
        lua_table = FakeLuaTable({1: "a", 2: "b"})
        assert primitive._lua_to_python(lua_table) == ["a", "b"]
    finally:
        sys.modules.pop("lupa", None)


def test_classify_lua_to_python_keeps_string_keys(monkeypatch):
    class FakeLuaTable:
        def __init__(self, items):
            self._items = items

        def items(self):
            return self._items.items()

    fake_lupa = SimpleNamespace(
        lua_type=lambda value: "table" if isinstance(value, FakeLuaTable) else "string"
    )
    monkeypatch.setitem(sys.modules, "lupa", fake_lupa)
    try:
        primitive = ClassifyPrimitive(agent_factory=create_mock_agent_factory(["Yes"]))
        lua_table = FakeLuaTable({"a": 1, 1: "b"})
        assert primitive._lua_to_python(lua_table) == {"a": 1, 1: "b"}
    finally:
        sys.modules.pop("lupa", None)


def test_classify_unknown_method_uses_factory():
    class CustomClassifier:
        def __init__(self, config=None, **kwargs):
            self.config = config or {}
            self.kwargs = kwargs
            self.classes = ["yes"]
            self.target_classes = []

        def classify(self, _text):
            return ClassifierResult(value="yes")

        def reset(self):
            return None

    ClassifierFactory.register("custom_test", CustomClassifier)
    primitive = ClassifyPrimitive(agent_factory=create_mock_agent_factory(["Yes"]))
    handle = primitive({"method": "custom_test"})
    assert isinstance(handle, ClassifyHandle)
