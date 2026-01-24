"""Tests for the Extract primitive with mocked agents."""

import pytest

from tactus.stdlib.extract.primitive import ExtractPrimitive, ExtractHandle
from tactus.stdlib.extract.llm import LLMExtractor
from tactus.stdlib.core.models import ExtractorResult


class MockAgentHandle:
    """Mock agent handle for testing."""

    def __init__(self, responses=None):
        self.responses = responses or ['{"name": "John"}']
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


class TestExtractPrimitive:
    """Tests for ExtractPrimitive."""

    def test_extract_requires_fields(self):
        """Extract should raise error if fields not provided."""
        factory = create_mock_agent_factory(['{"name": "John"}'])
        primitive = ExtractPrimitive(agent_factory=factory)

        with pytest.raises(ValueError, match="fields"):
            primitive({"prompt": "Test prompt"})

    def test_extract_requires_prompt(self):
        """Extract should raise error if prompt not provided."""
        factory = create_mock_agent_factory(['{"name": "John"}'])
        primitive = ExtractPrimitive(agent_factory=factory)

        with pytest.raises(ValueError, match="prompt"):
            primitive({"fields": {"name": "string"}})

    def test_one_shot_extraction(self):
        """Extract with input should return result directly."""
        factory = create_mock_agent_factory(['{"name": "John", "age": 30}'])
        primitive = ExtractPrimitive(agent_factory=factory)

        result = primitive(
            {
                "fields": {"name": "string", "age": "number"},
                "prompt": "Extract info",
                "input": "John is 30 years old",
            }
        )

        assert isinstance(result, dict)
        assert result["name"] == "John"
        assert result["age"] == 30

    def test_reusable_extractor(self):
        """Extract without input should return ExtractHandle."""
        factory = create_mock_agent_factory(['{"name": "John"}'])
        primitive = ExtractPrimitive(agent_factory=factory)

        result = primitive({"fields": {"name": "string"}, "prompt": "Extract name"})

        assert isinstance(result, ExtractHandle)

    def test_handle_can_be_called_multiple_times(self):
        """ExtractHandle should be callable multiple times."""
        responses = ['{"name": "John"}', '{"name": "Jane"}']
        factory = create_mock_agent_factory(responses)
        primitive = ExtractPrimitive(agent_factory=factory)

        handle = primitive({"fields": {"name": "string"}, "prompt": "Extract name"})

        result1 = handle("John Doe")
        assert result1.fields["name"] == "John"


class TestLLMExtractor:
    """Tests for LLMExtractor."""

    def test_basic_extraction(self):
        """LLMExtractor should extract fields from valid JSON response."""
        mock_agent = MockAgentHandle(['{"name": "John Smith", "age": 34}'])

        extractor = LLMExtractor(
            fields={"name": "string", "age": "number"},
            prompt="Extract name and age",
            agent_factory=lambda c: mock_agent,
        )
        extractor._agent = mock_agent

        result = extractor.extract("John Smith is 34 years old")

        assert result.fields["name"] == "John Smith"
        assert result.fields["age"] == 34
        assert result.retry_count == 0

    def test_string_type_coercion(self):
        """String fields should be coerced to strings."""
        mock_agent = MockAgentHandle(['{"value": 123}'])

        extractor = LLMExtractor(
            fields={"value": "string"},
            prompt="Extract value",
            agent_factory=lambda c: mock_agent,
        )
        extractor._agent = mock_agent

        result = extractor.extract("test")

        assert result.fields["value"] == "123"

    def test_number_type_validation(self):
        """Number fields should accept numeric values."""
        mock_agent = MockAgentHandle(['{"count": 42, "price": 19.99}'])

        extractor = LLMExtractor(
            fields={"count": "number", "price": "number"},
            prompt="Extract numbers",
            agent_factory=lambda c: mock_agent,
        )
        extractor._agent = mock_agent

        result = extractor.extract("test")

        assert result.fields["count"] == 42
        assert result.fields["price"] == 19.99

    def test_boolean_type_validation(self):
        """Boolean fields should be validated."""
        mock_agent = MockAgentHandle(['{"active": true, "verified": false}'])

        extractor = LLMExtractor(
            fields={"active": "boolean", "verified": "boolean"},
            prompt="Extract booleans",
            agent_factory=lambda c: mock_agent,
        )
        extractor._agent = mock_agent

        result = extractor.extract("test")

        assert result.fields["active"] is True
        assert result.fields["verified"] is False

    def test_list_type_validation(self):
        """List fields should accept arrays."""
        mock_agent = MockAgentHandle(['{"items": ["a", "b", "c"]}'])

        extractor = LLMExtractor(
            fields={"items": "list"},
            prompt="Extract list",
            agent_factory=lambda c: mock_agent,
        )
        extractor._agent = mock_agent

        result = extractor.extract("test")

        assert result.fields["items"] == ["a", "b", "c"]

    def test_missing_field_strict_mode(self):
        """Missing fields in strict mode should cause validation error."""
        mock_agent = MockAgentHandle(['{"name": "John"}', '{"name": "John", "age": 30}'])

        extractor = LLMExtractor(
            fields={"name": "string", "age": "number"},
            prompt="Extract info",
            strict=True,
            agent_factory=lambda c: mock_agent,
        )
        extractor._agent = mock_agent

        # First response missing 'age', should retry
        result = extractor.extract("test")

        # After retry, should have both fields
        assert result.fields["name"] == "John"
        assert result.fields["age"] == 30
        assert result.retry_count == 1

    def test_missing_field_non_strict_mode(self):
        """Missing fields in non-strict mode should be allowed."""
        mock_agent = MockAgentHandle(['{"name": "John"}'])

        extractor = LLMExtractor(
            fields={"name": "string", "age": "number"},
            prompt="Extract info",
            strict=False,
            agent_factory=lambda c: mock_agent,
        )
        extractor._agent = mock_agent

        result = extractor.extract("test")

        assert result.fields["name"] == "John"
        assert result.fields["age"] is None
        assert result.retry_count == 0

    def test_invalid_json_triggers_retry(self):
        """Invalid JSON should trigger retry."""
        mock_agent = MockAgentHandle(["This is not JSON", '{"name": "John"}'])

        extractor = LLMExtractor(
            fields={"name": "string"},
            prompt="Extract name",
            agent_factory=lambda c: mock_agent,
        )
        extractor._agent = mock_agent

        result = extractor.extract("test")

        assert result.fields["name"] == "John"
        assert result.retry_count == 1

    def test_max_retries_exceeded(self):
        """Should return error when max retries exceeded."""
        mock_agent = MockAgentHandle(["Invalid", "Still invalid", "More invalid", "Nope"])

        extractor = LLMExtractor(
            fields={"name": "string"},
            prompt="Extract name",
            max_retries=2,
            agent_factory=lambda c: mock_agent,
        )
        extractor._agent = mock_agent

        result = extractor.extract("test")

        assert result.error is not None
        assert "Max retries" in result.error
        assert result.retry_count == 2

    def test_json_embedded_in_text(self):
        """Should extract JSON embedded in text."""
        mock_agent = MockAgentHandle(
            ['Here is the extracted data: {"name": "John", "age": 30} as requested.']
        )

        extractor = LLMExtractor(
            fields={"name": "string", "age": "number"},
            prompt="Extract info",
            agent_factory=lambda c: mock_agent,
        )
        extractor._agent = mock_agent

        result = extractor.extract("test")

        assert result.fields["name"] == "John"
        assert result.fields["age"] == 30


class TestExtractHandle:
    """Tests for ExtractHandle."""

    def test_new_style_init(self):
        """Handle should accept extractor parameter."""
        mock_agent = MockAgentHandle(['{"name": "John"}'])
        extractor = LLMExtractor(
            fields={"name": "string"},
            prompt="Extract",
            agent_factory=lambda c: mock_agent,
        )

        handle = ExtractHandle(extractor=extractor)

        assert handle._extractor is extractor
        assert handle.fields == {"name": "string"}

    def test_callable_interface(self):
        """Handle should be callable."""
        mock_agent = MockAgentHandle(['{"name": "John"}'])
        extractor = LLMExtractor(
            fields={"name": "string"},
            prompt="Extract",
            agent_factory=lambda c: mock_agent,
        )
        extractor._agent = mock_agent

        handle = ExtractHandle(extractor=extractor)
        result = handle("test input")

        assert isinstance(result, ExtractorResult)
        assert result.fields["name"] == "John"

    def test_dict_input(self):
        """Handle should accept dict input with 'text' key."""
        mock_agent = MockAgentHandle(['{"name": "John"}'])
        extractor = LLMExtractor(
            fields={"name": "string"},
            prompt="Extract",
            agent_factory=lambda c: mock_agent,
        )
        extractor._agent = mock_agent

        handle = ExtractHandle(extractor=extractor)
        result = handle({"text": "test input"})

        assert result.fields["name"] == "John"


class TestExtractorResult:
    """Tests for ExtractorResult."""

    def test_to_dict(self):
        """Result should convert to dict with flattened fields."""
        result = ExtractorResult(
            fields={"name": "John", "age": 30},
            retry_count=1,
        )

        d = result.to_dict()

        assert d["name"] == "John"
        assert d["age"] == 30
        assert d["_retry_count"] == 1
        assert d["_error"] is None

    def test_is_valid_property(self):
        """is_valid should reflect validation state."""
        valid = ExtractorResult(fields={"name": "John"})
        assert valid.is_valid is True

        with_errors = ExtractorResult(
            fields={"name": "John"}, validation_errors=["Missing field: age"]
        )
        assert with_errors.is_valid is False

        with_error = ExtractorResult(fields={}, error="Something went wrong")
        assert with_error.is_valid is False


class TestExtractorInheritance:
    """Tests for extractor inheritance."""

    def test_llm_extractor_inherits_from_base(self):
        """LLMExtractor should inherit from BaseExtractor."""
        from tactus.stdlib.core.base import BaseExtractor

        mock_agent = MockAgentHandle(['{"name": "John"}'])
        extractor = LLMExtractor(
            fields={"name": "string"},
            prompt="Extract",
            agent_factory=lambda c: mock_agent,
        )

        assert isinstance(extractor, BaseExtractor)

    def test_callable_via_base_class_interface(self):
        """Extractor should be callable via __call__."""
        mock_agent = MockAgentHandle(['{"name": "John"}'])
        extractor = LLMExtractor(
            fields={"name": "string"},
            prompt="Extract",
            agent_factory=lambda c: mock_agent,
        )
        extractor._agent = mock_agent

        result = extractor("test input")

        assert isinstance(result, ExtractorResult)
        assert result.fields["name"] == "John"
