"""
Tests for LSP server implementation.
"""

import pytest
from lsp_server import LSPServer


@pytest.fixture
def lsp_server():
    """Create LSP server instance."""
    return LSPServer()


def test_initialize(lsp_server):
    """Test LSP initialize request."""
    message = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"capabilities": {}}}

    response = lsp_server.handle_message(message)

    assert response is not None
    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 1
    assert "result" in response
    assert "capabilities" in response["result"]
    assert lsp_server.initialized is True


def test_did_open_notification(lsp_server):
    """Test textDocument/didOpen notification."""
    # Initialize first
    init_message = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {"capabilities": {}},
    }
    lsp_server.handle_message(init_message)

    # Send didOpen
    message = {
        "jsonrpc": "2.0",
        "method": "textDocument/didOpen",
        "params": {
            "textDocument": {
                "uri": "file:///test.tac",
                "languageId": "tactus-lua",
                "version": 1,
                "text": 'name("test")\nprocedure(function() end)',
            }
        },
    }

    response = lsp_server.handle_message(message)

    # Notifications don't return responses
    assert response is None
    assert "file:///test.tac" in lsp_server.handler.documents


def test_did_change_notification(lsp_server):
    """Test textDocument/didChange notification."""
    # Initialize
    lsp_server.handle_message(
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"capabilities": {}}}
    )

    # Open document
    lsp_server.handle_message(
        {
            "jsonrpc": "2.0",
            "method": "textDocument/didOpen",
            "params": {"textDocument": {"uri": "file:///test.tac", "text": 'name("test")'}},
        }
    )

    # Change document
    message = {
        "jsonrpc": "2.0",
        "method": "textDocument/didChange",
        "params": {
            "textDocument": {"uri": "file:///test.tac", "version": 2},
            "contentChanges": [
                {"text": 'name("test")\nversion("1.0.0")\nprocedure(function() end)'}
            ],
        },
    }

    response = lsp_server.handle_message(message)

    assert response is None
    assert (
        lsp_server.handler.documents["file:///test.tac"]
        == 'name("test")\nversion("1.0.0")\nprocedure(function() end)'
    )


def test_completion_request(lsp_server):
    """Test textDocument/completion request."""
    # Initialize
    lsp_server.handle_message(
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"capabilities": {}}}
    )

    # Open document
    lsp_server.handle_message(
        {
            "jsonrpc": "2.0",
            "method": "textDocument/didOpen",
            "params": {"textDocument": {"uri": "file:///test.tac", "text": 'name("test")\n'}},
        }
    )

    # Request completions
    message = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "textDocument/completion",
        "params": {
            "textDocument": {"uri": "file:///test.tac"},
            "position": {"line": 1, "character": 0},
        },
    }

    response = lsp_server.handle_message(message)

    assert response is not None
    assert response["id"] == 2
    assert "result" in response
    assert "items" in response["result"]
    assert len(response["result"]["items"]) > 0

    # Check for DSL function completions
    labels = [item["label"] for item in response["result"]["items"]]
    assert "agent" in labels
    assert "procedure" in labels


def test_hover_request(lsp_server):
    """Test textDocument/hover request."""
    # Initialize
    lsp_server.handle_message(
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"capabilities": {}}}
    )

    # Open document with agent
    lsp_server.handle_message(
        {
            "jsonrpc": "2.0",
            "method": "textDocument/didOpen",
            "params": {
                "textDocument": {
                    "uri": "file:///test.tac",
                    "text": """name("test")
version("1.0.0")
agent("worker", {
    provider = "openai",
    model = "gpt-4o",
    system_prompt = "Test"
})
procedure(function() end)""",
                }
            },
        }
    )

    # Request hover
    message = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "textDocument/hover",
        "params": {
            "textDocument": {"uri": "file:///test.tac"},
            "position": {"line": 2, "character": 7},
        },
    }

    response = lsp_server.handle_message(message)

    assert response is not None
    assert response["id"] == 2
    # Hover may return None if not over a symbol
    # Just check it doesn't error


def test_error_handling(lsp_server):
    """Test error handling for unknown methods."""
    message = {"jsonrpc": "2.0", "id": 1, "method": "unknown/method", "params": {}}

    response = lsp_server.handle_message(message)

    assert response is not None
    assert "error" in response
    assert response["error"]["code"] == -32601  # Method not found


def test_validation_with_errors(lsp_server):
    """Test validation produces diagnostics for invalid code."""
    # Initialize
    lsp_server.handle_message(
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"capabilities": {}}}
    )

    # Open document with missing required fields
    lsp_server.handle_message(
        {
            "jsonrpc": "2.0",
            "method": "textDocument/didOpen",
            "params": {
                "textDocument": {
                    "uri": "file:///test.tac",
                    "text": 'version("1.0.0")\nprocedure(function() end)',  # Missing name
                }
            },
        }
    )

    # Diagnostics should be generated
    diagnostics = lsp_server.handler.validate_document(
        "file:///test.tac", 'version("1.0.0")\nprocedure(function() end)'
    )

    assert len(diagnostics) > 0
    # Should have error about missing name
    messages = [d["message"] for d in diagnostics]
    assert any("name is required" in msg.lower() for msg in messages)
