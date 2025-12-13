"""
Tactus IDE Backend Server - Simplified Version

Uses HTTP polling instead of WebSockets to avoid compatibility issues.
"""

import os
import logging
from pathlib import Path
from flask import Flask, request, jsonify
from flask_cors import CORS
from lsp_server import LSPServer

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

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
    """Handle file operations (read/write .tac files)."""
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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    logger.info(f"Starting Tactus IDE Backend (HTTP mode) on port {port}")
    app.run(host="127.0.0.1", port=port, debug=False, threaded=True)
