import importlib


class DummyH5py:
    class Dataset:
        pass

    class File:
        def __init__(self, path, mode):
            self.path = path
            self.mode = mode
            self.items = {"a": DummyH5py.Dataset(), "b": DummyH5py.Dataset()}

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def visititems(self, visitor):
            for name, obj in self.items.items():
                visitor(name, obj)


def test_hdf5_list_without_context(monkeypatch):
    module = importlib.import_module("tactus.stdlib.io.hdf5")
    monkeypatch.setattr(module, "_ctx", None, raising=False)
    monkeypatch.setattr(module, "h5py", DummyH5py)

    assert module.list("data.h5") == ["a", "b"]
