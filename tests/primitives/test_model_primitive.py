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

    assert model.predict({"x": 1}) == {"result": 1}
    backend.predict_sync.assert_called_once_with({"x": 1})


def test_predict_with_context_uses_checkpoint():
    backend = mock.Mock()
    backend.predict_sync.return_value = "ok"
    with mock.patch("tactus.backends.http_backend.HTTPModelBackend", return_value=backend):
        model = ModelPrimitive("m", {"type": "http", "endpoint": "http://example"})

    context = DummyContext()
    model.context = context
    assert model.predict({"x": 2}) == "ok"
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
    assert model.predict({"x": 2}) == "ok"
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

    assert model._execute_predict({"x": 4}) == "backend"
    backend.predict_sync.assert_called_once_with({"x": 4})


def test_call_alias_and_repr():
    backend = mock.Mock()
    backend.predict_sync.return_value = "backend"
    with mock.patch("tactus.backends.http_backend.HTTPModelBackend", return_value=backend):
        model = ModelPrimitive("m", {"type": "http", "endpoint": "http://example"})

    assert model({"x": 5}) == "backend"
    assert repr(model) == "ModelPrimitive(m, type=http)"
