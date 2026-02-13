"""
Tests for Model primitive input/output validation.
"""

import pytest
from pydantic import ValidationError
from unittest.mock import MagicMock

from tactus.primitives.model import ModelPrimitive


class TestModelInputValidation:
    """Test Model primitive input schema validation."""

    def test_input_validation_success(self):
        """Test valid input passes validation."""
        config = {
            "type": "http",
            "endpoint": "http://test.com/predict",
            "input": {"text": "string", "count": "int"},
        }

        model = ModelPrimitive("test_model", config)

        # Mock the backend
        model.backend.predict_sync = MagicMock(return_value={"label": "positive"})

        # Valid input should work
        result = model.predict({"text": "hello", "count": 5})
        assert result == {"label": "positive"}

        # Verify backend was called with validated input
        model.backend.predict_sync.assert_called_once()

    def test_input_validation_failure(self):
        """Test invalid input raises ValidationError."""
        config = {
            "type": "http",
            "endpoint": "http://test.com/predict",
            "input": {"text": "string", "count": "int"},
        }

        model = ModelPrimitive("test_model", config)
        model.backend.predict_sync = MagicMock()

        # Invalid input - string that can't be coerced to int
        with pytest.raises(ValidationError) as exc_info:
            model.predict({"text": "hello", "count": "definitely_not_an_int"})

        # Backend should not have been called
        model.backend.predict_sync.assert_not_called()

        # Error message should mention the field
        assert "count" in str(exc_info.value)

    def test_missing_required_field(self):
        """Test missing required field raises ValidationError."""
        config = {
            "type": "http",
            "endpoint": "http://test.com/predict",
            "input": {"text": "string", "count": "int"},
        }

        model = ModelPrimitive("test_model", config)
        model.backend.predict_sync = MagicMock()

        # Missing 'count' field
        with pytest.raises(ValidationError):
            model.predict({"text": "hello"})

    def test_no_input_schema_no_validation(self):
        """Test model without input schema doesn't validate."""
        config = {
            "type": "http",
            "endpoint": "http://test.com/predict",
            # No input schema
        }

        model = ModelPrimitive("test_model", config)
        model.backend.predict_sync = MagicMock(return_value={"result": "ok"})

        # Any input should work
        result = model.predict({"anything": "goes"})
        assert result == {"result": "ok"}

        result = model.predict("string input")
        assert result == {"result": "ok"}


class TestModelOutputValidation:
    """Test Model primitive output schema validation."""

    def test_output_validation_warning(self, caplog):
        """Test invalid output logs warning but doesn't fail."""
        import logging

        config = {
            "type": "http",
            "endpoint": "http://test.com/predict",
            "output": {"label": "string", "confidence": "float"},
        }

        model = ModelPrimitive("test_model", config)

        # Backend returns invalid output (string that can't be coerced to float)
        model.backend.predict_sync = MagicMock(
            return_value={"label": "positive", "confidence": "definitely_not_a_float"}
        )

        # Should not raise, but should log warning
        with caplog.at_level(logging.WARNING):
            result = model.predict({"text": "hello"})

        # Result is returned unchanged despite validation failure
        assert result == {"label": "positive", "confidence": "definitely_not_a_float"}

        # Warning was logged
        assert "output validation failed" in caplog.text.lower()

    def test_output_validation_success(self):
        """Test valid output passes without warnings."""
        config = {
            "type": "http",
            "endpoint": "http://test.com/predict",
            "output": {"label": "string", "confidence": "float"},
        }

        model = ModelPrimitive("test_model", config)
        model.backend.predict_sync = MagicMock(
            return_value={"label": "positive", "confidence": 0.95}
        )

        result = model.predict({"text": "hello"})
        assert result == {"label": "positive", "confidence": 0.95}

    def test_no_output_schema_no_validation(self):
        """Test model without output schema doesn't validate."""
        config = {
            "type": "http",
            "endpoint": "http://test.com/predict",
            # No output schema
        }

        model = ModelPrimitive("test_model", config)

        # Backend can return anything
        model.backend.predict_sync = MagicMock(return_value={"random": "data", "any": "structure"})

        result = model.predict({"text": "hello"})
        assert result == {"random": "data", "any": "structure"}


class TestSchemaResolution:
    """Test schema resolution during ModelPrimitive initialization."""

    def test_invalid_schema_raises_valueerror(self):
        """Test invalid schema specification raises ValueError."""
        config = {
            "type": "http",
            "endpoint": "http://test.com/predict",
            "input": 123,  # Invalid: not a dict or string
        }

        with pytest.raises(ValueError, match="Failed to resolve schema"):
            ModelPrimitive("test_model", config)

    def test_nonexistent_python_class_raises_valueerror(self):
        """Test nonexistent Python class reference raises ValueError."""
        config = {
            "type": "http",
            "endpoint": "http://test.com/predict",
            "input": "nonexistent.module.ClassName",
        }

        with pytest.raises(ValueError, match="Failed to resolve schema"):
            ModelPrimitive("test_model", config)
