"""
Tactus IDE Backend Server.

Provides HTTP-based LSP server for the Tactus IDE.
"""

import logging
from pathlib import Path
from flask import Flask, request, jsonify
from flask_cors import CORS
from typing import Dict, Any, List, Optional

from tactus.validation.validator import TactusValidator, ValidationMode
from tactus.core.registry import ValidationMessage

logger = logging.getLogger(__name__)


class TactusLSPHandler:
    """LSP handler for Tactus DSL."""

    def __init__(self):
        self.validator = TactusValidator()
        self.documents: Dict[str, str] = {}
        self.registries: Dict[str, Any] = {}

    def validate_document(self, uri: str, text: str) -> List[Dict[str, Any]]:
        """Validate document and return LSP diagnostics."""
        self.documents[uri] = text

        try:
            result = self.validator.validate(text, ValidationMode.FULL)

            if result.registry:
                self.registries[uri] = result.registry

            diagnostics = []
            for error in result.errors:
                diagnostic = self._convert_to_diagnostic(error, "Error")
                if diagnostic:
                    diagnostics.append(diagnostic)

            for warning in result.warnings:
                diagnostic = self._convert_to_diagnostic(warning, "Warning")
                if diagnostic:
                    diagnostics.append(diagnostic)

            return diagnostics
        except Exception as e:
            logger.error(f"Error validating document {uri}: {e}", exc_info=True)
            return []

    def _convert_to_diagnostic(
        self, message: ValidationMessage, severity_str: str
    ) -> Optional[Dict[str, Any]]:
        """Convert ValidationMessage to LSP diagnostic."""
        severity = 1 if severity_str == "Error" else 2

        line = message.location[0] - 1 if message.location else 0
        col = message.location[1] - 1 if len(message.location) > 1 else 0

        return {
            "range": {
                "start": {"line": line, "character": col},
                "end": {"line": line, "character": col + 10},
            },
            "severity": severity,
            "source": "tactus",
            "message": message.message,
        }

    def close_document(self, uri: str):
        """Close a document."""
        self.documents.pop(uri, None)
        self.registries.pop(uri, None)


class LSPServer:
    """Language Server Protocol server for Tactus DSL."""

    def __init__(self):
        self.handler = TactusLSPHandler()
        self.initialized = False
        self.client_capabilities = {}

    def handle_message(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Handle LSP JSON-RPC message."""
        method = message.get("method")
        params = message.get("params", {})
        msg_id = message.get("id")

        try:
            if method == "initialize":
                result = self._handle_initialize(params)
            else:
                logger.warning(f"Unhandled LSP method: {method}")
                return self._error_response(msg_id, -32601, f"Method not found: {method}")

            if msg_id is not None:
                return {"jsonrpc": "2.0", "id": msg_id, "result": result}
        except Exception as e:
            logger.error(f"Error handling {method}: {e}", exc_info=True)
            return self._error_response(msg_id, -32603, str(e))

    def _handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle initialize request."""
        self.client_capabilities = params.get("capabilities", {})
        self.initialized = True

        return {
            "capabilities": {
                "textDocumentSync": {"openClose": True, "change": 2, "save": {"includeText": True}},
                "diagnosticProvider": {
                    "interFileDependencies": False,
                    "workspaceDiagnostics": False,
                },
            },
            "serverInfo": {"name": "tactus-lsp-server", "version": "0.1.0"},
        }

    def _error_response(self, msg_id: Optional[int], code: int, message: str) -> Dict[str, Any]:
        """Create LSP error response."""
        return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


def create_app():
    """Create and configure the Flask app."""
    app = Flask(__name__)
    CORS(app)

    # Initialize LSP server
    lsp_server = LSPServer()

    @app.route("/health", methods=["GET"])
    def health():
        """Health check endpoint."""
        return jsonify({"status": "ok", "service": "tactus-ide-backend"})

    @app.route("/api/file", methods=["GET", "POST"])
    def file_operations():
        """Handle file operations (read/write .tactus.lua files)."""
        if request.method == "GET":
            file_path = request.args.get("path")
            if not file_path:
                return jsonify({"error": "Missing 'path' parameter"}), 400

            try:
                path = Path(file_path)
                if not path.exists():
                    return jsonify({"error": f"File not found: {file_path}"}), 404

                content = path.read_text()
                return jsonify({"path": str(path), "content": content, "name": path.name})
            except Exception as e:
                logger.error(f"Error reading file {file_path}: {e}")
                return jsonify({"error": str(e)}), 500

        elif request.method == "POST":
            data = request.json
            file_path = data.get("path")
            content = data.get("content")

            if not file_path or content is None:
                return jsonify({"error": "Missing 'path' or 'content'"}), 400

            try:
                path = Path(file_path)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
                return jsonify({"success": True, "path": str(path)})
            except Exception as e:
                logger.error(f"Error writing file {file_path}: {e}")
                return jsonify({"error": str(e)}), 500

    @app.route("/api/lsp", methods=["POST"])
    def lsp_request():
        """Handle LSP requests via HTTP."""
        try:
            message = request.json
            logger.debug(f"Received LSP message: {message.get('method')}")
            response = lsp_server.handle_message(message)

            if response:
                return jsonify(response)
            return jsonify({"jsonrpc": "2.0", "id": message.get("id"), "result": None})
        except Exception as e:
            logger.error(f"Error handling LSP message: {e}")
            return (
                jsonify(
                    {
                        "jsonrpc": "2.0",
                        "id": message.get("id"),
                        "error": {"code": -32603, "message": str(e)},
                    }
                ),
                500,
            )

    @app.route("/api/lsp/notification", methods=["POST"])
    def lsp_notification():
        """Handle LSP notifications via HTTP and return diagnostics."""
        try:
            message = request.json
            method = message.get("method")
            params = message.get("params", {})

            logger.debug(f"Received LSP notification: {method}")

            # Handle notifications that produce diagnostics
            diagnostics = []
            if method == "textDocument/didOpen":
                text_document = params.get("textDocument", {})
                uri = text_document.get("uri")
                text = text_document.get("text")
                if uri and text:
                    diagnostics = lsp_server.handler.validate_document(uri, text)
            elif method == "textDocument/didChange":
                text_document = params.get("textDocument", {})
                content_changes = params.get("contentChanges", [])
                uri = text_document.get("uri")
                if uri and content_changes:
                    text = content_changes[0].get("text") if content_changes else None
                    if text:
                        diagnostics = lsp_server.handler.validate_document(uri, text)
            elif method == "textDocument/didClose":
                text_document = params.get("textDocument", {})
                uri = text_document.get("uri")
                if uri:
                    lsp_server.handler.close_document(uri)

            # Return diagnostics if any
            if diagnostics:
                return jsonify({"status": "ok", "diagnostics": diagnostics})

            return jsonify({"status": "ok"})
        except Exception as e:
            logger.error(f"Error handling LSP notification: {e}")
            return jsonify({"error": str(e)}), 500

    return app
