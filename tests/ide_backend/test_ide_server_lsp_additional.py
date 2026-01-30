from types import SimpleNamespace

from tactus.ide import server as ide_server


def test_lsp_handler_close_document_removes_state():
    handler = ide_server.TactusLSPHandler()
    handler.documents["file://test"] = "data"
    handler.registries["file://test"] = {"ok": True}

    handler.close_document("file://test")

    assert "file://test" not in handler.documents
    assert "file://test" not in handler.registries


def test_lsp_handle_message_method_not_found():
    server = ide_server.LSPServer()
    response = server.handle_message({"id": 1, "method": "unknown"})

    assert response["error"]["code"] == -32601


def test_lsp_handle_message_without_id_returns_none():
    server = ide_server.LSPServer()
    response = server.handle_message({"method": "initialize"})

    assert response is None


def test_lsp_handle_message_exception_returns_error(monkeypatch):
    server = ide_server.LSPServer()

    def boom(_params):
        raise RuntimeError("boom")

    monkeypatch.setattr(server, "_handle_initialize", boom)
    response = server.handle_message({"id": 1, "method": "initialize"})

    assert response["error"]["code"] == -32603


def test_lsp_handler_convert_to_diagnostic_defaults():
    handler = ide_server.TactusLSPHandler()
    message = SimpleNamespace(location=None, message="bad")

    diagnostic = handler._convert_to_diagnostic(message, "Warning")
    assert diagnostic["severity"] == 2
    assert diagnostic["range"]["start"]["line"] == 0
