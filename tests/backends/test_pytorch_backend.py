import builtins
import contextlib
import sys
import asyncio

import pytest

from tactus.backends.pytorch_backend import PyTorchModelBackend


class FakeTensor:
    def __init__(self, data, *, dim_value=None, numel_value=1):
        self._data = data
        self._dim_value = dim_value
        self._numel_value = numel_value

    def to(self, device):
        return self

    def dim(self):
        if self._dim_value is not None:
            return self._dim_value
        return 2 if isinstance(self._data, list) else 0

    def argmax(self, dim=-1):
        return FakeTensor(1)

    def item(self):
        return int(self._data) if not isinstance(self._data, list) else 0

    def numel(self):
        return self._numel_value

    def cpu(self):
        return self

    def numpy(self):
        return self

    def tolist(self):
        return self._data if isinstance(self._data, list) else [self._data]


class FakeModel:
    def __init__(self, return_value=None):
        self._return_value = return_value or FakeTensor([0.1, 0.9])

    def eval(self):
        return None

    def __call__(self, input_tensor):
        return self._return_value


def test_load_model_missing_torch(monkeypatch, tmp_path):
    def fake_import(name, *args, **kwargs):
        if name == "torch":
            raise ImportError("no torch")
        return original_import(name, *args, **kwargs)

    original_import = builtins.__import__
    monkeypatch.setattr(builtins, "__import__", fake_import)

    backend = PyTorchModelBackend(str(tmp_path / "model.pt"))
    with pytest.raises(ImportError):
        backend._load_model()


def test_predict_sync_with_fake_torch(monkeypatch, tmp_path):
    fake_torch = type(
        "torch",
        (),
        {},
    )()
    fake_torch.Tensor = FakeTensor
    fake_torch.tensor = lambda data: FakeTensor(data)
    fake_torch.no_grad = contextlib.nullcontext
    fake_torch.load = lambda path, map_location=None: FakeModel()

    monkeypatch.setitem(sys.modules, "torch", fake_torch)

    model_path = tmp_path / "model.pt"
    model_path.write_text("x")

    backend = PyTorchModelBackend(str(model_path), labels=["neg", "pos"])
    result = backend.predict_sync([1, 2, 3])
    assert result == "pos"


def test_load_model_missing_file(monkeypatch, tmp_path):
    fake_torch = type("torch", (), {})()
    fake_torch.load = lambda path, map_location=None: FakeModel()

    monkeypatch.setitem(sys.modules, "torch", fake_torch)

    backend = PyTorchModelBackend(str(tmp_path / "missing.pt"))
    with pytest.raises(FileNotFoundError):
        backend._load_model()


def test_load_model_skips_when_already_loaded(monkeypatch, tmp_path):
    fake_torch = type("torch", (), {})()
    fake_torch.load = lambda path, map_location=None: FakeModel()

    monkeypatch.setitem(sys.modules, "torch", fake_torch)

    model_path = tmp_path / "model.pt"
    model_path.write_text("x")

    backend = PyTorchModelBackend(str(model_path))
    backend.model = object()
    backend._load_model()


def test_predict_async_runs_sync(monkeypatch, tmp_path):
    fake_torch = type("torch", (), {})()
    fake_torch.Tensor = FakeTensor
    fake_torch.tensor = lambda data: FakeTensor(data)
    fake_torch.no_grad = contextlib.nullcontext
    fake_torch.load = lambda path, map_location=None: FakeModel(FakeTensor(4))

    monkeypatch.setitem(sys.modules, "torch", fake_torch)

    model_path = tmp_path / "model.pt"
    model_path.write_text("x")

    backend = PyTorchModelBackend(str(model_path))
    assert asyncio.run(backend.predict(1)) == 4


def test_predict_sync_missing_torch_raises(monkeypatch, tmp_path):
    backend = PyTorchModelBackend(str(tmp_path / "model.pt"))
    backend.model = FakeModel()

    original_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "torch":
            raise ImportError("no torch")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(ImportError, match="PyTorch not installed"):
        backend.predict_sync(1)


def test_predict_sync_accepts_tensor_input(monkeypatch, tmp_path):
    fake_torch = type("torch", (), {})()
    fake_torch.Tensor = FakeTensor
    fake_torch.tensor = lambda data: FakeTensor(data)
    fake_torch.no_grad = contextlib.nullcontext
    fake_torch.load = lambda path, map_location=None: FakeModel(FakeTensor(5))

    monkeypatch.setitem(sys.modules, "torch", fake_torch)

    model_path = tmp_path / "model.pt"
    model_path.write_text("x")

    backend = PyTorchModelBackend(str(model_path))
    input_tensor = FakeTensor([1, 2])
    assert backend.predict_sync(input_tensor) == 5


def test_predict_sync_returns_raw_scalar(monkeypatch, tmp_path):
    fake_torch = type("torch", (), {})()
    fake_torch.Tensor = FakeTensor
    fake_torch.tensor = lambda data: FakeTensor(data)
    fake_torch.no_grad = contextlib.nullcontext
    fake_torch.load = lambda path, map_location=None: FakeModel(FakeTensor(3))

    monkeypatch.setitem(sys.modules, "torch", fake_torch)

    model_path = tmp_path / "model.pt"
    model_path.write_text("x")

    backend = PyTorchModelBackend(str(model_path))
    assert backend.predict_sync(1) == 3


def test_predict_sync_returns_raw_list(monkeypatch, tmp_path):
    fake_torch = type("torch", (), {})()
    fake_torch.Tensor = FakeTensor
    fake_torch.tensor = lambda data: FakeTensor(data)
    fake_torch.no_grad = contextlib.nullcontext
    fake_torch.load = lambda path, map_location=None: FakeModel(FakeTensor([1, 2], numel_value=2))

    monkeypatch.setitem(sys.modules, "torch", fake_torch)

    model_path = tmp_path / "model.pt"
    model_path.write_text("x")

    backend = PyTorchModelBackend(str(model_path))
    assert backend.predict_sync(1) == [1, 2]


def test_predict_sync_label_out_of_range_returns_index(monkeypatch, tmp_path):
    fake_torch = type("torch", (), {})()
    fake_torch.Tensor = FakeTensor
    fake_torch.tensor = lambda data: FakeTensor(data)
    fake_torch.no_grad = contextlib.nullcontext
    fake_torch.load = lambda path, map_location=None: FakeModel(FakeTensor([0.1, 0.9]))

    monkeypatch.setitem(sys.modules, "torch", fake_torch)

    model_path = tmp_path / "model.pt"
    model_path.write_text("x")

    backend = PyTorchModelBackend(str(model_path), labels=["only"])
    assert backend.predict_sync([1, 2, 3]) == 1


def test_predict_sync_label_rounds_scalar(monkeypatch, tmp_path):
    class FloatTensor(FakeTensor):
        def item(self):
            return 1.6

    fake_torch = type("torch", (), {})()
    fake_torch.Tensor = FakeTensor
    fake_torch.tensor = lambda data: FakeTensor(data)
    fake_torch.no_grad = contextlib.nullcontext
    fake_torch.load = lambda path, map_location=None: FakeModel(FloatTensor(1.6, dim_value=0))

    monkeypatch.setitem(sys.modules, "torch", fake_torch)

    model_path = tmp_path / "model.pt"
    model_path.write_text("x")

    backend = PyTorchModelBackend(str(model_path), labels=["neg", "pos", "maybe"])
    assert backend.predict_sync(1) == "maybe"
