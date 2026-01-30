import importlib


class DummyContext:
    def __init__(self, validated):
        self.validated = validated
        self.calls = []

    def validate_path(self, path):
        self.calls.append(path)
        return self.validated


def test_exists_without_context(tmp_path, monkeypatch):
    module = importlib.import_module("tactus.stdlib.io.file")
    data_path = tmp_path / "data.txt"
    data_path.write_text("hi", encoding="utf-8")
    monkeypatch.setattr(module, "_ctx", None, raising=False)

    assert module.exists(str(data_path)) is True


def test_exists_uses_context(tmp_path, monkeypatch):
    module = importlib.import_module("tactus.stdlib.io.file")
    data_path = tmp_path / "data.txt"
    data_path.write_text("hi", encoding="utf-8")
    ctx = DummyContext(str(data_path))
    monkeypatch.setattr(module, "_ctx", ctx, raising=False)

    assert module.exists("data.txt") is True
    assert ctx.calls == ["data.txt"]
