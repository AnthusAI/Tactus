from unittest import mock

import pytest

from tactus.primitives.model import ModelPrimitive


class DummyContext:
    def __init__(self):
        self.calls = []

    def checkpoint(self, fn, checkpoint_type, source_info=None):
        self.calls.append(
            {
                "checkpoint_type": checkpoint_type,
                "source_info": source_info,
            }
        )
        return fn()


class DummyMockManager:
    def __init__(self, result=None):
        self.result = result
        self.recorded = []

    def get_mock_response(self, model_name, args):
        return self.result

    def record_call(self, model_name, args, result):
        self.recorded.append((model_name, args, result))


def test_create_backend_http(monkeypatch):
    backend = object()
    with mock.patch("tactus.backends.http_backend.HTTPModelBackend", return_value=backend):
        model = ModelPrimitive("m", {"type": "http", "endpoint": "http://example"})
    assert model.backend is backend


def test_create_backend_pytorch(monkeypatch):
    backend = object()
    with mock.patch("tactus.backends.pytorch_backend.PyTorchModelBackend", return_value=backend):
        model = ModelPrimitive("m", {"type": "pytorch", "path": "/tmp/model"})
    assert model.backend is backend


def test_create_backend_unknown_raises():
    with pytest.raises(ValueError, match="Unknown model type"):
        ModelPrimitive("m", {"type": "unknown"})


def test_predict_without_context_calls_backend():
    backend = mock.Mock()
    backend.predict_sync.return_value = {"result": 1}
    with mock.patch("tactus.backends.http_backend.HTTPModelBackend", return_value=backend):
        model = ModelPrimitive("m", {"type": "http", "endpoint": "http://example"})

    result = model.predict({"x": 1})
    assert result.output == {"result": 1}
    assert result.backend_type == "http"
    backend.predict_sync.assert_called_once_with({"x": 1})


def test_predict_with_context_uses_checkpoint():
    backend = mock.Mock()
    backend.predict_sync.return_value = "ok"
    with mock.patch("tactus.backends.http_backend.HTTPModelBackend", return_value=backend):
        model = ModelPrimitive("m", {"type": "http", "endpoint": "http://example"})

    context = DummyContext()
    model.context = context
    result = model.predict({"x": 2})
    assert result.output == "ok"
    assert context.calls[0]["checkpoint_type"] == "model_predict"
    assert context.calls[0]["source_info"] is not None


def test_predict_with_context_without_frame(monkeypatch):
    backend = mock.Mock()
    backend.predict_sync.return_value = "ok"
    with mock.patch("tactus.backends.http_backend.HTTPModelBackend", return_value=backend):
        model = ModelPrimitive("m", {"type": "http", "endpoint": "http://example"})

    context = DummyContext()
    model.context = context

    def fake_currentframe():
        class Frame:
            f_back = None

        return Frame()

    monkeypatch.setattr("inspect.currentframe", fake_currentframe)
    result = model.predict({"x": 2})
    assert result.output == "ok"
    assert context.calls[0]["source_info"] is None


def test_execute_predict_uses_mock_manager():
    backend = mock.Mock()
    backend.predict_sync.return_value = "backend"
    mock_manager = DummyMockManager(result="mocked")
    with mock.patch("tactus.backends.http_backend.HTTPModelBackend", return_value=backend):
        model = ModelPrimitive("m", {"type": "http", "endpoint": "http://example"})
    model.mock_manager = mock_manager

    assert model._execute_predict({"x": 3}) == "mocked"
    assert mock_manager.recorded
    backend.predict_sync.assert_not_called()


def test_execute_predict_ignores_record_call_errors():
    backend = mock.Mock()
    backend.predict_sync.return_value = "backend"

    class ExplodingMockManager(DummyMockManager):
        def record_call(self, model_name, args, result):
            raise RuntimeError("boom")

    mock_manager = ExplodingMockManager(result="mocked")
    with mock.patch("tactus.backends.http_backend.HTTPModelBackend", return_value=backend):
        model = ModelPrimitive("m", {"type": "http", "endpoint": "http://example"})
    model.mock_manager = mock_manager

    assert model._execute_predict({"x": 3}) == "mocked"
    backend.predict_sync.assert_not_called()


def test_execute_predict_falls_back_to_backend():
    backend = mock.Mock()
    backend.predict_sync.return_value = "backend"
    mock_manager = DummyMockManager(result=None)
    with mock.patch("tactus.backends.http_backend.HTTPModelBackend", return_value=backend):
        model = ModelPrimitive("m", {"type": "http", "endpoint": "http://example"})
    model.mock_manager = mock_manager

    result = model._execute_predict({"x": 4})
    assert result.output == "backend"
    backend.predict_sync.assert_called_once_with({"x": 4})


def test_call_alias_and_repr():
    backend = mock.Mock()
    backend.predict_sync.return_value = "backend"
    with mock.patch("tactus.backends.http_backend.HTTPModelBackend", return_value=backend):
        model = ModelPrimitive("m", {"type": "http", "endpoint": "http://example"})

    result = model({"x": 5})
    assert result.output == "backend"
    assert repr(model) == "ModelPrimitive(m, type=http)"


def test_create_backend_llm():
    """Test creating LLM backend."""
    backend = object()
    with mock.patch("tactus.backends.llm_backend.LLMModelBackend", return_value=backend):
        model = ModelPrimitive(
            "m",
            {
                "type": "llm",
                "model": "openai/gpt-4o-mini",
                "system_prompt": "Classify sentiment",
            },
        )
    assert model.backend is backend


def test_execute_predict_with_llm_backend_format():
    """Test that LLM backend format (with 'result' and 'cost' keys) is properly processed."""
    backend = mock.Mock()
    backend.predict_sync.return_value = {
        "result": {"label": "positive"},
        "cost": {"total_cost": 0.0002, "prompt_cost": 0.0001, "completion_cost": 0.0001},
        "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
    }
    with mock.patch("tactus.backends.http_backend.HTTPModelBackend", return_value=backend):
        model = ModelPrimitive("m", {"type": "http", "endpoint": "http://example"})

    result = model._execute_predict({"text": "Great!"})

    assert result.output == {"label": "positive"}
    assert result.cost.inference_cost == 0.0002
    assert result.cost.tokens_in == 10
    assert result.cost.tokens_out == 10
    assert result.backend_type == "http"


def test_execute_predict_with_non_dict_input():
    """Test input validation with non-dict input and single-field schema."""
    from pydantic import ValidationError

    backend = mock.Mock()
    backend.predict_sync.return_value = {"result": "ok"}
    with mock.patch("tactus.backends.http_backend.HTTPModelBackend", return_value=backend):
        model = ModelPrimitive(
            "m",
            {
                "type": "http",
                "endpoint": "http://example",
                "input": {"input": "string"},  # Single field named "input"
            },
        )

    # Should wrap non-dict input in dict with "input" key
    result = model._execute_predict("test string")
    assert result.output == {"result": "ok"}
    backend.predict_sync.assert_called_once_with("test string")


def test_execute_predict_with_non_dict_output():
    """Test output validation with non-dict output."""
    backend = mock.Mock()
    backend.predict_sync.return_value = "string result"  # Non-dict output
    with mock.patch("tactus.backends.http_backend.HTTPModelBackend", return_value=backend):
        model = ModelPrimitive(
            "m",
            {
                "type": "http",
                "endpoint": "http://example",
                "output": {"output": "string"},  # Schema expects dict with "output" field
            },
        )

    # Should log warning but not fail
    result = model._execute_predict({"x": 1})
    assert result.output == "string result"


def test_cumulative_statistics():
    """Test cumulative cost and timing statistics."""
    backend = mock.Mock()
    # First call
    backend.predict_sync.return_value = {
        "result": {"label": "positive"},
        "cost": {"total_cost": 0.001},
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }

    with mock.patch("tactus.backends.http_backend.HTTPModelBackend", return_value=backend):
        model = ModelPrimitive("m", {"type": "http", "endpoint": "http://example"})

    # Before any predictions
    assert model.total_cost == 0.0
    assert model.prediction_count == 0
    assert model.avg_latency_ms == 0.0

    # First prediction
    model._execute_predict({"x": 1})

    assert model.total_cost == 0.001
    assert model.prediction_count == 1
    assert model.avg_latency_ms > 0

    # Second call
    backend.predict_sync.return_value = {
        "result": {"label": "negative"},
        "cost": {"total_cost": 0.002},
        "usage": {"prompt_tokens": 15, "completion_tokens": 8, "total_tokens": 23},
    }

    model._execute_predict({"x": 2})

    assert model.total_cost == 0.003
    assert model.prediction_count == 2
    assert model.avg_latency_ms > 0


def test_cost_tracking_with_none_values():
    """Test that None cost values don't break statistics tracking."""
    backend = mock.Mock()
    # Backend returns result without cost info (compute_time_ms will be set, but inference_cost will be None)
    backend.predict_sync.return_value = "simple result"

    with mock.patch("tactus.backends.http_backend.HTTPModelBackend", return_value=backend):
        model = ModelPrimitive("m", {"type": "http", "endpoint": "http://example"})

    model._execute_predict({"x": 1})

    # Cost should still be 0.0 (no inference cost)
    assert model.total_cost == 0.0
    assert model.prediction_count == 1
    # But latency should be tracked
    assert model.avg_latency_ms > 0


def test_create_backend_registry():
    """Test creating registry backend."""
    backend = object()
    with mock.patch("tactus.backends.registry_backend.RegistryBackend", return_value=backend):
        model = ModelPrimitive(
            "m",
            {
                "type": "registry",
                "name": "classifier",
                "version": "champion",
            },
        )
    assert model.backend is backend
