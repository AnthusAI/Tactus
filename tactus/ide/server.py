"""
Tactus IDE Backend Server.

Provides HTTP-based LSP server for the Tactus IDE.
"""

import logging
import os
import subprocess
import threading
import time
import queue as q
from pathlib import Path
from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS
from typing import Dict, Any, List, Optional

from tactus.validation.validator import TactusValidator, ValidationMode
from tactus.core.registry import ValidationMessage

logger = logging.getLogger(__name__)

# Workspace state
WORKSPACE_ROOT = None


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
        col = message.location[1] - 1 if message.location and len(message.location) > 1 else 0

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


def _resolve_workspace_path(relative_path: str) -> Path:
    """
    Resolve a relative path within the workspace root.
    Raises ValueError if path escapes workspace or workspace not set.
    """
    global WORKSPACE_ROOT
    
    if not WORKSPACE_ROOT:
        raise ValueError("No workspace folder selected")
    
    # Normalize the relative path
    workspace = Path(WORKSPACE_ROOT).resolve()
    target = (workspace / relative_path).resolve()
    
    # Ensure target is within workspace (prevent path traversal)
    try:
        target.relative_to(workspace)
    except ValueError:
        raise ValueError(f"Path '{relative_path}' escapes workspace")
    
    return target


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

    @app.route("/api/workspace/cwd", methods=["GET"])
    def get_cwd():
        """Get current working directory."""
        return jsonify({"cwd": str(Path.cwd())})

    @app.route("/api/workspace", methods=["GET", "POST"])
    def workspace_operations():
        """Handle workspace operations."""
        global WORKSPACE_ROOT
        
        if request.method == "GET":
            if not WORKSPACE_ROOT:
                return jsonify({"root": None, "name": None})
            
            workspace_path = Path(WORKSPACE_ROOT)
            return jsonify({
                "root": str(workspace_path),
                "name": workspace_path.name
            })
        
        elif request.method == "POST":
            data = request.json
            root = data.get("root")
            
            if not root:
                return jsonify({"error": "Missing 'root' parameter"}), 400
            
            try:
                root_path = Path(root).resolve()
                
                if not root_path.exists():
                    return jsonify({"error": f"Path does not exist: {root}"}), 404
                
                if not root_path.is_dir():
                    return jsonify({"error": f"Path is not a directory: {root}"}), 400
                
                # Set workspace root and change working directory
                WORKSPACE_ROOT = str(root_path)
                os.chdir(WORKSPACE_ROOT)
                
                logger.info(f"Workspace set to: {WORKSPACE_ROOT}")
                
                return jsonify({
                    "success": True,
                    "root": WORKSPACE_ROOT,
                    "name": root_path.name
                })
            except Exception as e:
                logger.error(f"Error setting workspace {root}: {e}")
                return jsonify({"error": str(e)}), 500

    @app.route("/api/tree", methods=["GET"])
    def tree_operations():
        """List directory contents within the workspace."""
        global WORKSPACE_ROOT
        
        if not WORKSPACE_ROOT:
            return jsonify({"error": "No workspace folder selected"}), 400
        
        relative_path = request.args.get("path", "")
        
        try:
            target_path = _resolve_workspace_path(relative_path)
            
            if not target_path.exists():
                return jsonify({"error": f"Path not found: {relative_path}"}), 404
            
            if not target_path.is_dir():
                return jsonify({"error": f"Path is not a directory: {relative_path}"}), 400
            
            # List directory contents
            entries = []
            for item in sorted(target_path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
                entry = {
                    "name": item.name,
                    "path": str(item.relative_to(WORKSPACE_ROOT)),
                    "type": "directory" if item.is_dir() else "file"
                }
                
                # Add extension for files
                if item.is_file():
                    entry["extension"] = item.suffix
                
                entries.append(entry)
            
            return jsonify({
                "path": relative_path,
                "entries": entries
            })
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            logger.error(f"Error listing directory {relative_path}: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/file", methods=["GET", "POST"])
    def file_operations():
        """Handle file operations (read/write files within workspace)."""
        if request.method == "GET":
            file_path = request.args.get("path")
            if not file_path:
                return jsonify({"error": "Missing 'path' parameter"}), 400
            
            try:
                path = _resolve_workspace_path(file_path)
                
                if not path.exists():
                    return jsonify({"error": f"File not found: {file_path}"}), 404
                
                if not path.is_file():
                    return jsonify({"error": f"Path is not a file: {file_path}"}), 400
                
                content = path.read_text()
                return jsonify({
                    "path": file_path,
                    "absolutePath": str(path),
                    "content": content,
                    "name": path.name
                })
            except ValueError as e:
                return jsonify({"error": str(e)}), 400
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
                path = _resolve_workspace_path(file_path)
                
                # Create parent directories if needed
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
                
                return jsonify({
                    "success": True,
                    "path": file_path,
                    "absolutePath": str(path)
                })
            except ValueError as e:
                return jsonify({"error": str(e)}), 400
            except Exception as e:
                logger.error(f"Error writing file {file_path}: {e}")
                return jsonify({"error": str(e)}), 500

    @app.route("/api/validate", methods=["POST"])
    def validate_procedure():
        """Validate Tactus procedure code."""
        data = request.json
        content = data.get("content")
        file_path = data.get("path", "untitled.tactus.lua")
        
        if content is None:
            return jsonify({"error": "Missing 'content' parameter"}), 400
        
        try:
            validator = TactusValidator()
            result = validator.validate(content)
            
            return jsonify({
                "valid": result.is_valid,
                "errors": [
                    {
                        "message": err.message,
                        "line": err.location[0] if err.location else None,
                        "column": err.location[1] if err.location else None,
                        "severity": err.severity
                    }
                    for err in result.errors
                ]
            })
        except Exception as e:
            logger.error(f"Error validating code: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/run", methods=["POST"])
    def run_procedure():
        """Run a Tactus procedure."""
        data = request.json
        file_path = data.get("path")
        content = data.get("content")
        
        if not file_path:
            return jsonify({"error": "Missing 'path' parameter"}), 400
        
        try:
            # Resolve path within workspace
            path = _resolve_workspace_path(file_path)
            
            # Save content if provided
            if content is not None:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
            
            # Ensure file exists
            if not path.exists():
                return jsonify({"error": f"File not found: {file_path}"}), 404
            
            # Run the procedure using tactus CLI
            result = subprocess.run(
                ["tactus", "run", str(path)],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=WORKSPACE_ROOT
            )
            
            return jsonify({
                "success": result.returncode == 0,
                "exitCode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr
            })
        except subprocess.TimeoutExpired:
            return jsonify({"error": "Procedure execution timed out (30s)"}), 408
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            logger.error(f"Error running procedure {file_path}: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/run/stream", methods=["GET"])
    def run_procedure_stream():
        """
        Run a Tactus procedure with SSE streaming output.
        
        Query param:
        - path: workspace-relative path to procedure file (required)
        """
        file_path = request.args.get("path")
        
        if not file_path:
            return jsonify({"error": "Missing 'path' parameter"}), 400
        
        try:
            # Resolve path within workspace
            path = _resolve_workspace_path(file_path)
            
            # Ensure file exists
            if not path.exists():
                return jsonify({"error": f"File not found: {file_path}"}), 404
            
            procedure_id = f"ide-{path.stem}"
            
            def generate_events():
                """Generator function that yields SSE events."""
                log_handler = None
                try:
                    # Send start event
                    import json
                    from datetime import datetime
                    from tactus.adapters.ide_log import IDELogHandler
                    from tactus.core.runtime import TactusRuntime
                    from tactus.adapters.file_storage import FileStorage
                    
                    start_event = {
                        "event_type": "execution",
                        "lifecycle_stage": "start",
                        "procedure_id": procedure_id,
                        "timestamp": datetime.utcnow().isoformat() + 'Z',
                        "details": {"path": file_path}
                    }
                    yield f"data: {json.dumps(start_event)}\n\n"
                    
                    # Create IDE log handler to collect structured events
                    log_handler = IDELogHandler()
                    
                    # Create storage backend
                    from pathlib import Path as PathLib
                    storage_dir = str(PathLib(WORKSPACE_ROOT) / ".tactus" / "storage") if WORKSPACE_ROOT else "~/.tactus/storage"
                    storage_backend = FileStorage(storage_dir=storage_dir)
                    
                    # Create runtime with log handler
                    runtime = TactusRuntime(
                        procedure_id=procedure_id,
                        storage_backend=storage_backend,
                        hitl_handler=None,  # No HITL in IDE streaming mode
                        log_handler=log_handler,
                    )
                    
                    # Read procedure source
                    source = path.read_text()
                    
                    # Run in a thread to avoid blocking
                    import asyncio
                    result_container = {"result": None, "error": None, "done": False}
                    
                    def run_procedure():
                        try:
                            # Create new event loop for this thread
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            result = loop.run_until_complete(runtime.execute(source, format="lua"))
                            result_container["result"] = result
                        except Exception as e:
                            result_container["error"] = e
                        finally:
                            result_container["done"] = True
                            loop.close()
                    
                    exec_thread = threading.Thread(target=run_procedure)
                    exec_thread.daemon = True
                    exec_thread.start()
                    
                    # Stream log events as they arrive
                    while not result_container["done"]:
                        # Get log events from handler
                        events = log_handler.get_events(timeout=0.1)
                        for event in events:
                            try:
                                # Serialize with ISO format for datetime
                                event_dict = event.model_dump(mode='json')
                                # Add 'Z' suffix to indicate UTC timezone
                                event_dict['timestamp'] = event.timestamp.isoformat() + 'Z' if not event.timestamp.isoformat().endswith('Z') else event.timestamp.isoformat()
                                yield f"data: {json.dumps(event_dict)}\n\n"
                            except Exception as e:
                                logger.error(f"Error serializing event: {e}", exc_info=True)
                                logger.error(f"Event type: {type(event)}, Event: {event}")
                        
                        time.sleep(0.05)
                    
                    # Get any remaining events
                    events = log_handler.get_events(timeout=0.1)
                    for event in events:
                        try:
                            # Serialize with ISO format for datetime
                            event_dict = event.model_dump(mode='json')
                            # Add 'Z' suffix to indicate UTC timezone
                            event_dict['timestamp'] = event.timestamp.isoformat() + 'Z' if not event.timestamp.isoformat().endswith('Z') else event.timestamp.isoformat()
                            yield f"data: {json.dumps(event_dict)}\n\n"
                        except Exception as e:
                            logger.error(f"Error serializing event: {e}", exc_info=True)
                            logger.error(f"Event type: {type(event)}, Event: {event}")
                    
                    # Wait for thread to finish
                    exec_thread.join(timeout=1)
                    
                    # Send completion event
                    if result_container["error"]:
                        complete_event = {
                            "event_type": "execution",
                            "lifecycle_stage": "error",
                            "procedure_id": procedure_id,
                            "exit_code": 1,
                            "timestamp": datetime.utcnow().isoformat() + 'Z',
                            "details": {"success": False, "error": str(result_container["error"])}
                        }
                    else:
                        complete_event = {
                            "event_type": "execution",
                            "lifecycle_stage": "complete",
                            "procedure_id": procedure_id,
                            "exit_code": 0,
                            "timestamp": datetime.utcnow().isoformat() + 'Z',
                            "details": {"success": True}
                        }
                    yield f"data: {json.dumps(complete_event)}\n\n"
                    
                except Exception as e:
                    logger.error(f"Error in streaming execution: {e}", exc_info=True)
                    error_event = {
                        "event_type": "execution",
                        "lifecycle_stage": "error",
                        "procedure_id": procedure_id,
                        "timestamp": datetime.utcnow().isoformat() + 'Z',
                        "details": {"error": str(e)}
                    }
                    yield f"data: {json.dumps(error_event)}\n\n"
            
            return Response(
                stream_with_context(generate_events()),
                mimetype="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                    "Connection": "keep-alive"
                }
            )
            
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            logger.error(f"Error setting up streaming execution: {e}", exc_info=True)
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


def main() -> None:
    """
    Run the IDE backend server.

    This enables `python -m tactus.ide.server` which is useful for local development
    and file-watcher based auto-reload workflows.
    """
    logging.basicConfig(level=os.environ.get("TACTUS_IDE_LOG_LEVEL", "INFO"))

    host = os.environ.get("TACTUS_IDE_HOST", "127.0.0.1")
    port_str = os.environ.get("TACTUS_IDE_PORT", "5001")
    try:
        port = int(port_str)
    except ValueError:
        raise SystemExit(f"Invalid TACTUS_IDE_PORT: {port_str!r}")

    app = create_app()
    # NOTE: We intentionally disable Flask's reloader here; external watchers (e.g. watchdog)
    # should restart this process to avoid double-fork behavior.
    app.run(host=host, port=port, debug=False, threaded=True, use_reloader=False)


if __name__ == "__main__":
    main()


