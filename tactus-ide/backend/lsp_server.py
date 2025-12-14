"""
LSP Server implementation for Tactus IDE.

Implements the Language Server Protocol for semantic validation and intelligence.
Syntax validation is handled client-side by the TypeScript parser.
"""

import logging
from typing import Dict, Any, Optional, List
from tactus_lsp_handler import TactusLSPHandler

logger = logging.getLogger(__name__)


class LSPServer:
    """
    Language Server Protocol server for Tactus DSL.

    Handles LSP JSON-RPC messages and delegates to TactusLSPHandler
    for Tactus-specific logic.
    """

    def __init__(self):
        self.handler = TactusLSPHandler()
        self.initialized = False
        self.client_capabilities = {}

    def handle_message(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Handle LSP JSON-RPC message and return response.

        Args:
            message: LSP message dict with jsonrpc, id, method, params

        Returns:
            Response dict or None for notifications
        """
        method = message.get("method")
        params = message.get("params", {})
        msg_id = message.get("id")

        try:
            if method == "initialize":
                result = self._handle_initialize(params)
            elif method == "textDocument/didOpen":
                result = self._handle_did_open(params)
                return None  # Notification, no response
            elif method == "textDocument/didChange":
                result = self._handle_did_change(params)
                return None  # Notification, no response
            elif method == "textDocument/completion":
                result = self._handle_completion(params)
            elif method == "textDocument/hover":
                result = self._handle_hover(params)
            elif method == "textDocument/signatureHelp":
                result = self._handle_signature_help(params)
            else:
                logger.warning(f"Unhandled LSP method: {method}")
                return self._error_response(msg_id, -32601, f"Method not found: {method}")

            if msg_id is not None:
                return {"jsonrpc": "2.0", "id": msg_id, "result": result}
        except Exception as e:
            logger.error(f"Error handling {method}: {e}", exc_info=True)
            return self._error_response(msg_id, -32603, str(e))

    def handle_notification(self, message: Dict[str, Any]):
        """Handle LSP notification (no response expected)."""
        method = message.get("method")
        params = message.get("params", {})

        if method == "textDocument/didOpen":
            self._handle_did_open(params)
        elif method == "textDocument/didChange":
            self._handle_did_change(params)
        elif method == "textDocument/didClose":
            self._handle_did_close(params)

    def _handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle initialize request."""
        self.client_capabilities = params.get("capabilities", {})
        self.initialized = True

        return {
            "capabilities": {
                "textDocumentSync": {
                    "openClose": True,
                    "change": 2,  # Incremental
                    "save": {"includeText": True},
                },
                "completionProvider": {
                    "resolveProvider": False,
                    "triggerCharacters": ["(", "{", '"', "."],
                },
                "hoverProvider": True,
                "signatureHelpProvider": {"triggerCharacters": ["(", ","]},
                "diagnosticProvider": {
                    "interFileDependencies": False,
                    "workspaceDiagnostics": False,
                },
            },
            "serverInfo": {"name": "tactus-lsp-server", "version": "0.1.0"},
        }

    def _handle_did_open(self, params: Dict[str, Any]):
        """Handle textDocument/didOpen notification."""
        text_document = params.get("textDocument", {})
        uri = text_document.get("uri")
        text = text_document.get("text")

        if uri and text:
            # Validate document and send diagnostics
            diagnostics = self.handler.validate_document(uri, text)
            self._publish_diagnostics(uri, diagnostics)

    def _handle_did_change(self, params: Dict[str, Any]):
        """Handle textDocument/didChange notification."""
        text_document = params.get("textDocument", {})
        content_changes = params.get("contentChanges", [])
        uri = text_document.get("uri")

        if uri and content_changes:
            # Get full text from changes (we use full sync)
            text = content_changes[0].get("text") if content_changes else None
            if text:
                # Validate and send diagnostics
                diagnostics = self.handler.validate_document(uri, text)
                self._publish_diagnostics(uri, diagnostics)

    def _handle_did_close(self, params: Dict[str, Any]):
        """Handle textDocument/didClose notification."""
        text_document = params.get("textDocument", {})
        uri = text_document.get("uri")

        if uri:
            self.handler.close_document(uri)

    def _handle_completion(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle textDocument/completion request."""
        text_document = params.get("textDocument", {})
        position = params.get("position", {})
        uri = text_document.get("uri")

        if uri:
            items = self.handler.get_completions(uri, position)
            return {"isIncomplete": False, "items": items}

        return {"isIncomplete": False, "items": []}

    def _handle_hover(self, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Handle textDocument/hover request."""
        text_document = params.get("textDocument", {})
        position = params.get("position", {})
        uri = text_document.get("uri")

        if uri:
            hover_info = self.handler.get_hover(uri, position)
            return hover_info

        return None

    def _handle_signature_help(self, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Handle textDocument/signatureHelp request."""
        text_document = params.get("textDocument", {})
        position = params.get("position", {})
        uri = text_document.get("uri")

        if uri:
            signature_help = self.handler.get_signature_help(uri, position)
            return signature_help

        return None

    def _publish_diagnostics(self, uri: str, diagnostics: List[Dict[str, Any]]):
        """
        Publish diagnostics to client.

        Note: This needs to be sent via the WebSocket connection.
        In practice, this will be handled by the Flask-SocketIO emit.
        """
        # This is called from handle_message, diagnostics will be sent
        # via the notification mechanism
        pass

    def _error_response(self, msg_id: Optional[int], code: int, message: str) -> Dict[str, Any]:
        """Create LSP error response."""
        return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}
