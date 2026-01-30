import importlib
import json as json_lib


class DummyContext:
    def __init__(self, validated):
        self.validated = validated
        self.calls = []

    def validate_path(self, path):
        self.calls.append(path)
        return self.validated


def test_json_read_and_write_use_context(tmp_path, monkeypatch):
    module = importlib.import_module("tactus.stdlib.io.json")
    data_path = tmp_path / "data.json"
    ctx = DummyContext(str(data_path))
    monkeypatch.setattr(module, "_ctx", ctx, raising=False)

    module.write("data.json", {"key": "value"})
    assert ctx.calls == ["data.json"]
    assert json_lib.loads(data_path.read_text(encoding="utf-8")) == {"key": "value"}

    ctx.calls.clear()
    assert module.read("data.json") == {"key": "value"}
    assert ctx.calls == ["data.json"]


def test_csv_write_supports_custom_headers_and_context(tmp_path, monkeypatch):
    module = importlib.import_module("tactus.stdlib.io.csv")
    data_path = tmp_path / "data.csv"
    ctx = DummyContext(str(data_path))
    monkeypatch.setattr(module, "_ctx", ctx, raising=False)

    module.write(
        "data.csv",
        [{"b": "2", "a": "1"}],
        options={"headers": ["a", "b"]},
    )
    assert ctx.calls == ["data.csv"]
    assert data_path.read_text(encoding="utf-8").splitlines() == ["a,b", "1,2"]


def test_csv_read_without_context(tmp_path, monkeypatch):
    module = importlib.import_module("tactus.stdlib.io.csv")
    data_path = tmp_path / "data.csv"
    data_path.write_text("a,b\n1,2\n", encoding="utf-8")
    monkeypatch.setattr(module, "_ctx", None, raising=False)

    assert module.read(str(data_path)) == [{"a": "1", "b": "2"}]


def test_csv_read_uses_context(tmp_path, monkeypatch):
    module = importlib.import_module("tactus.stdlib.io.csv")
    data_path = tmp_path / "data.csv"
    data_path.write_text("a,b\n1,2\n", encoding="utf-8")
    ctx = DummyContext(str(data_path))
    monkeypatch.setattr(module, "_ctx", ctx, raising=False)

    assert module.read("data.csv") == [{"a": "1", "b": "2"}]
    assert ctx.calls == ["data.csv"]


def test_tsv_write_defaults_headers_and_context(tmp_path, monkeypatch):
    module = importlib.import_module("tactus.stdlib.io.tsv")
    data_path = tmp_path / "data.tsv"
    ctx = DummyContext(str(data_path))
    monkeypatch.setattr(module, "_ctx", ctx, raising=False)

    module.write("data.tsv", [{"a": "1", "b": "2"}])
    assert ctx.calls == ["data.tsv"]
    assert data_path.read_text(encoding="utf-8").splitlines() == ["a\tb", "1\t2"]


def test_tsv_read_without_context(tmp_path, monkeypatch):
    module = importlib.import_module("tactus.stdlib.io.tsv")
    data_path = tmp_path / "data.tsv"
    data_path.write_text("a\tb\n1\t2\n", encoding="utf-8")
    monkeypatch.setattr(module, "_ctx", None, raising=False)

    assert module.read(str(data_path)) == [{"a": "1", "b": "2"}]


def test_tsv_read_uses_context(tmp_path, monkeypatch):
    module = importlib.import_module("tactus.stdlib.io.tsv")
    data_path = tmp_path / "data.tsv"
    data_path.write_text("a\tb\n1\t2\n", encoding="utf-8")
    ctx = DummyContext(str(data_path))
    monkeypatch.setattr(module, "_ctx", ctx, raising=False)

    assert module.read("data.tsv") == [{"a": "1", "b": "2"}]
    assert ctx.calls == ["data.tsv"]


def test_json_read_without_context(tmp_path, monkeypatch):
    module = importlib.import_module("tactus.stdlib.io.json")
    data_path = tmp_path / "data.json"
    data_path.write_text('{"key": "value"}', encoding="utf-8")
    monkeypatch.setattr(module, "_ctx", None, raising=False)

    assert module.read(str(data_path)) == {"key": "value"}


def test_json_write_without_context(tmp_path, monkeypatch):
    module = importlib.import_module("tactus.stdlib.io.json")
    data_path = tmp_path / "out.json"
    monkeypatch.setattr(module, "_ctx", None, raising=False)

    module.write(str(data_path), {"ok": True})
    assert json_lib.loads(data_path.read_text(encoding="utf-8")) == {"ok": True}


def test_csv_write_without_context(tmp_path, monkeypatch):
    module = importlib.import_module("tactus.stdlib.io.csv")
    data_path = tmp_path / "out.csv"
    monkeypatch.setattr(module, "_ctx", None, raising=False)

    module.write(str(data_path), [{"a": "1"}])
    assert data_path.read_text(encoding="utf-8").splitlines() == ["a", "1"]


def test_tsv_write_without_context(tmp_path, monkeypatch):
    module = importlib.import_module("tactus.stdlib.io.tsv")
    data_path = tmp_path / "out.tsv"
    monkeypatch.setattr(module, "_ctx", None, raising=False)

    module.write(str(data_path), [{"a": "1"}])
    assert data_path.read_text(encoding="utf-8").splitlines() == ["a", "1"]
