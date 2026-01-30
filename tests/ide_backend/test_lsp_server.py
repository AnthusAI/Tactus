import sys
from pathlib import Path

BACKEND_PATH = Path(__file__).resolve().parents[2] / "tactus-ide" / "backend"
sys.path.insert(0, str(BACKEND_PATH))

from lsp_server import LSPServer  # noqa: E402


def test_lsp_server_initialize_response():
    server = LSPServer()

    response = server.handle_message({"id": 1, "method": "initialize", "params": {}})

    assert response["result"]["serverInfo"]["name"] == "tactus-lsp-server"
    assert server.initialized is True


def test_lsp_server_completion_and_hover():
    server = LSPServer()

    server.handler.get_completions = lambda uri, pos: [{"label": "agent"}]
    server.handler.get_hover = lambda uri, pos: {"contents": "hover"}

    completion = server.handle_message(
        {"id": 2, "method": "textDocument/completion", "params": {"textDocument": {"uri": "u"}}}
    )
    hover = server.handle_message(
        {"id": 3, "method": "textDocument/hover", "params": {"textDocument": {"uri": "u"}}}
    )

    assert completion["result"]["items"][0]["label"] == "agent"
    assert hover["result"]["contents"] == "hover"


def test_lsp_server_notifications_do_not_return_response():
    server = LSPServer()

    server.handler.validate_document = lambda uri, text: []

    opened = server.handle_message(
        {
            "method": "textDocument/didOpen",
            "params": {"textDocument": {"uri": "u", "text": "content"}},
        }
    )
    changed = server.handle_message(
        {
            "method": "textDocument/didChange",
            "params": {
                "textDocument": {"uri": "u"},
                "contentChanges": [{"text": "content"}],
            },
        }
    )

    assert opened is None
    assert changed is None


def test_lsp_server_unknown_method_errors():
    server = LSPServer()

    response = server.handle_message({"id": 4, "method": "unknown", "params": {}})

    assert response["error"]["code"] == -32601


def test_lsp_server_handle_notification_close():
    server = LSPServer()
    closed = {}

    server.handler.close_document = lambda uri: closed.setdefault("uri", uri)

    server.handle_notification(
        {"method": "textDocument/didClose", "params": {"textDocument": {"uri": "u"}}}
    )

    assert closed["uri"] == "u"


def test_lsp_server_signature_help_and_missing_uri_paths():
    server = LSPServer()

    server.handler.get_signature_help = lambda uri, pos: {"signatures": ["sig"]}

    signature = server.handle_message(
        {"id": 5, "method": "textDocument/signatureHelp", "params": {"textDocument": {"uri": "u"}}}
    )
    missing = server.handle_message(
        {"id": 6, "method": "textDocument/signatureHelp", "params": {"textDocument": {}}}
    )

    assert signature["result"]["signatures"] == ["sig"]
    assert missing["result"] is None


def test_lsp_server_completion_hover_without_uri_returns_empty():
    server = LSPServer()

    completion = server.handle_message(
        {"id": 7, "method": "textDocument/completion", "params": {"textDocument": {}}}
    )
    hover = server.handle_message(
        {"id": 8, "method": "textDocument/hover", "params": {"textDocument": {}}}
    )

    assert completion["result"]["items"] == []
    assert hover["result"] is None


def test_lsp_server_did_open_missing_fields_no_validation():
    server = LSPServer()
    called = {"count": 0}

    server.handler.validate_document = lambda uri, text: called.__setitem__("count", 1)

    server.handle_message({"method": "textDocument/didOpen", "params": {"textDocument": {}}})

    assert called["count"] == 0


def test_lsp_server_did_change_missing_text_no_validation():
    server = LSPServer()
    called = {"count": 0}

    server.handler.validate_document = lambda uri, text: called.__setitem__("count", 1)

    server.handle_message(
        {
            "method": "textDocument/didChange",
            "params": {"textDocument": {"uri": "u"}, "contentChanges": [{}]},
        }
    )

    assert called["count"] == 0


def test_lsp_server_handle_notification_open_and_change():
    server = LSPServer()
    received = []

    server.handler.validate_document = lambda uri, text: received.append((uri, text)) or []

    server.handle_notification(
        {"method": "textDocument/didOpen", "params": {"textDocument": {"uri": "u", "text": "t"}}}
    )
    server.handle_notification(
        {
            "method": "textDocument/didChange",
            "params": {"textDocument": {"uri": "u"}, "contentChanges": [{"text": "c"}]},
        }
    )

    assert received == [("u", "t"), ("u", "c")]


def test_lsp_server_handle_message_error_response():
    server = LSPServer()

    def boom(_params):
        raise RuntimeError("boom")

    server._handle_completion = boom

    response = server.handle_message({"id": 9, "method": "textDocument/completion", "params": {}})

    assert response["error"]["code"] == -32603
    assert "boom" in response["error"]["message"]


def test_lsp_server_handle_message_without_id_returns_none():
    server = LSPServer()
    server.handler.get_completions = lambda uri, pos: []

    response = server.handle_message(
        {"method": "textDocument/completion", "params": {"textDocument": {"uri": "u"}}}
    )

    assert response is None


def test_lsp_server_did_change_without_uri_or_changes():
    server = LSPServer()
    called = {"count": 0}

    server.handler.validate_document = lambda uri, text: called.__setitem__("count", 1)

    server.handle_message(
        {
            "method": "textDocument/didChange",
            "params": {"textDocument": {"uri": "u"}, "contentChanges": []},
        }
    )
    server.handle_message(
        {
            "method": "textDocument/didChange",
            "params": {"textDocument": {}, "contentChanges": [{"text": "x"}]},
        }
    )

    assert called["count"] == 0


def test_lsp_server_did_close_without_uri():
    server = LSPServer()
    called = {"count": 0}

    server.handler.close_document = lambda uri: called.__setitem__("count", called["count"] + 1)

    server.handle_notification({"method": "textDocument/didClose", "params": {"textDocument": {}}})

    assert called["count"] == 0


def test_lsp_server_handle_notification_unknown_method_noop():
    server = LSPServer()

    server.handle_notification({"method": "workspace/didChangeConfiguration", "params": {}})
