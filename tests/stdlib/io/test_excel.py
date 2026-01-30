import importlib


class DummyContext:
    def __init__(self, validated):
        self.validated = validated
        self.calls = []

    def validate_path(self, path):
        self.calls.append(path)
        return self.validated


class DummyWorkbook:
    def __init__(self, sheetnames):
        self.sheetnames = sheetnames


def test_excel_sheets_without_context(monkeypatch):
    module = importlib.import_module("tactus.stdlib.io.excel")
    monkeypatch.setattr(module, "_ctx", None, raising=False)

    def fake_loader(path, read_only=True):
        return DummyWorkbook(["Sheet1", "Sheet2"])

    monkeypatch.setattr(module, "load_workbook", fake_loader)

    assert module.sheets("data.xlsx") == ["Sheet1", "Sheet2"]


def test_excel_sheets_uses_context(monkeypatch):
    module = importlib.import_module("tactus.stdlib.io.excel")
    ctx = DummyContext("validated.xlsx")
    monkeypatch.setattr(module, "_ctx", ctx, raising=False)

    captured = {}

    def fake_loader(path, read_only=True):
        captured["path"] = path
        return DummyWorkbook(["Main"])

    monkeypatch.setattr(module, "load_workbook", fake_loader)

    assert module.sheets("data.xlsx") == ["Main"]
    assert ctx.calls == ["data.xlsx"]
    assert captured["path"] == "validated.xlsx"
