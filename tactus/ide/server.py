"""
Tactus IDE Backend Server.

Provides HTTP-based LSP server for the Tactus IDE.
"""

import json
import logging
import os
import queue
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS
from typing import Any, Optional

from tactus.validation.validator import TactusValidator, ValidationMode
from tactus.core.registry import ValidationMessage

logger = logging.getLogger(__name__)

# Workspace state
WORKSPACE_ROOT = None

# Global cache clearing function - set by create_app()
_clear_runtime_caches_fn = None


def clear_runtime_caches():
    """Clear cached runtime instances. Must be called after create_app() initializes."""
    if _clear_runtime_caches_fn:
        _clear_runtime_caches_fn()
    else:
        logger.warning("clear_runtime_caches called but no implementation set")


class TactusLSPHandler:
    """LSP handler for Tactus DSL."""

    def __init__(self):
        self.validator = TactusValidator()
        self.documents: dict[str, str] = {}
        self.registries: dict[str, Any] = {}

    def validate_document(self, uri: str, text: str) -> list[dict[str, Any]]:
        """Validate document and return LSP diagnostics."""
        self.documents[uri] = text

        try:
            result = self.validator.validate(text, ValidationMode.FULL)

            if result.registry:
                self.registries[uri] = result.registry

            diagnostics: list[dict[str, Any]] = []
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
            logger.error("Error validating document %s: %s", uri, e, exc_info=True)
            return []

    def _convert_to_diagnostic(
        self, message: ValidationMessage, severity_str: str
    ) -> Optional[dict[str, Any]]:
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

    def handle_message(self, message: dict[str, Any]) -> Optional[dict[str, Any]]:
        """Handle LSP JSON-RPC message."""
        method = message.get("method")
        params = message.get("params", {})
        msg_id = message.get("id")

        try:
            if method == "initialize":
                result = self._handle_initialize(params)
            else:
                logger.warning("Unhandled LSP method: %s", method)
                return self._error_response(msg_id, -32601, f"Method not found: {method}")

            if msg_id is not None:
                return {"jsonrpc": "2.0", "id": msg_id, "result": result}
        except Exception as e:
            logger.error("Error handling %s: %s", method, e, exc_info=True)
            return self._error_response(msg_id, -32603, str(e))

    def _handle_initialize(self, params: dict[str, Any]) -> dict[str, Any]:
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

    def _error_response(self, msg_id: Optional[int], code: int, message: str) -> dict[str, Any]:
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


def create_app(initial_workspace: Optional[str] = None, frontend_dist_dir: Optional[str] = None):
    """Create and configure the Flask app.

    Args:
        initial_workspace: Initial workspace directory. If not provided, uses current directory.
        frontend_dist_dir: Path to frontend dist directory. If provided, serves frontend from Flask.
    """
    global WORKSPACE_ROOT

    # Configure Flask to serve frontend static files if provided
    if frontend_dist_dir:
        app = Flask(__name__, static_folder=frontend_dist_dir, static_url_path="")
    else:
        app = Flask(__name__)
    CORS(app)

    # Set initial workspace if provided
    if initial_workspace:
        WORKSPACE_ROOT = str(Path(initial_workspace).resolve())

    # Initialize LSP server
    lsp_server = LSPServer()

    @app.route("/health", methods=["GET"])
    def health():
        """Health check endpoint."""
        return jsonify({"status": "ok", "service": "tactus-ide-backend"})

    @app.route("/api/workspace/cwd", methods=["GET"])
    def get_cwd():
        """Get current working directory (returns the initial workspace if set)."""
        if WORKSPACE_ROOT:
            return jsonify({"cwd": WORKSPACE_ROOT})
        return jsonify({"cwd": str(Path.cwd())})

    @app.route("/api/about", methods=["GET"])
    def get_about_info():
        """Get application version and metadata."""
        from tactus import __version__

        return jsonify(
            {
                "version": __version__,
                "name": "Tactus IDE",
                "description": "A Lua-based DSL for agentic workflows",
                "author": "Ryan Porter",
                "license": "MIT",
                "repository": "https://github.com/AnthusAI/Tactus",
                "documentation": "https://github.com/AnthusAI/Tactus/tree/main/docs",
                "issues": "https://github.com/AnthusAI/Tactus/issues",
            }
        )

    @app.route("/api/workspace", methods=["GET", "POST"])
    def workspace_operations():
        """Handle workspace operations."""
        global WORKSPACE_ROOT

        if request.method == "GET":
            if not WORKSPACE_ROOT:
                return jsonify({"root": None, "name": None})

            workspace_path = Path(WORKSPACE_ROOT)
            return jsonify({"root": str(workspace_path), "name": workspace_path.name})

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

                logger.info("Workspace set to: %s", WORKSPACE_ROOT)

                return jsonify({"success": True, "root": WORKSPACE_ROOT, "name": root_path.name})
            except Exception as e:
                logger.error("Error setting workspace %s: %s", root, e)
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
            for item in sorted(
                target_path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())
            ):
                entry = {
                    "name": item.name,
                    "path": str(item.relative_to(WORKSPACE_ROOT)),
                    "type": "directory" if item.is_dir() else "file",
                }

                # Add extension for files
                if item.is_file():
                    entry["extension"] = item.suffix

                entries.append(entry)

            return jsonify({"path": relative_path, "entries": entries})
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            logger.error("Error listing directory %s: %s", relative_path, e)
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
                return jsonify(
                    {
                        "path": file_path,
                        "absolutePath": str(path),
                        "content": content,
                        "name": path.name,
                    }
                )
            except ValueError as e:
                return jsonify({"error": str(e)}), 400
            except Exception as e:
                logger.error("Error reading file %s: %s", file_path, e)
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

                return jsonify({"success": True, "path": file_path, "absolutePath": str(path)})
            except ValueError as e:
                return jsonify({"error": str(e)}), 400
            except Exception as e:
                logger.error("Error writing file %s: %s", file_path, e)
                return jsonify({"error": str(e)}), 500

    @app.route("/api/procedure/metadata", methods=["GET"])
    def get_procedure_metadata():
        """
        Get metadata about a procedure file using TactusValidator.

        Query params:
        - path: workspace-relative path to procedure file (required)

        Returns:
            {
                "success": true,
                "metadata": {
                    "description": str | null,
                    "input": { name: ParameterDeclaration },
                    "output": { name: OutputFieldDeclaration },
                    "agents": { name: AgentDeclaration },
                    "toolsets": { name: dict },
                    "tools": [str]  # Flattened list of all tools
                }
            }
        """
        file_path = request.args.get("path")

        if not file_path:
            return jsonify({"error": "Missing 'path' parameter"}), 400

        try:
            # Resolve path
            path = _resolve_workspace_path(file_path)

            if not path.exists():
                return jsonify({"error": f"File not found: {file_path}"}), 404

            # Validate with FULL mode to get registry
            validator = TactusValidator()
            result = validator.validate_file(str(path), ValidationMode.FULL)

            if not result.registry:
                # Validation failed or no registry
                return (
                    jsonify(
                        {
                            "success": False,
                            "error": "Failed to extract metadata",
                            "validation_errors": [
                                {
                                    "message": e.message,
                                    "line": e.location[0] if e.location else None,
                                }
                                for e in result.errors
                            ],
                        }
                    ),
                    400,
                )

            registry = result.registry

            # Extract tools from agents, toolsets, and lua_tools
            all_tools = set()
            for agent in registry.agents.values():
                all_tools.update(agent.tools)
            for toolset in registry.toolsets.values():
                if isinstance(toolset, dict) and "tools" in toolset:
                    all_tools.update(toolset["tools"])
            # Include Lua-defined tools (from tool() function calls)
            if hasattr(registry, "lua_tools") and registry.lua_tools:
                all_tools.update(registry.lua_tools.keys())

            # Parse specifications if present
            specifications_data = None
            if registry.gherkin_specifications:
                import re

                gherkin_text = registry.gherkin_specifications

                # Count scenarios
                scenarios = re.findall(r"^\s*Scenario:", gherkin_text, re.MULTILINE)

                # Extract feature name
                feature_match = re.search(r"Feature:\s*(.+)", gherkin_text)
                feature_name = feature_match.group(1).strip() if feature_match else None

                specifications_data = {
                    "text": gherkin_text,
                    "feature_name": feature_name,
                    "scenario_count": len(scenarios),
                }

            # Extract evaluations summary
            evaluations_data = None
            if registry.pydantic_evaluations:
                evals = registry.pydantic_evaluations
                dataset_count = 0
                evaluator_count = 0

                if isinstance(evals, dict):
                    # Count dataset items
                    if "dataset" in evals and isinstance(evals["dataset"], list):
                        dataset_count = len(evals["dataset"])

                    # Count evaluators
                    if "evaluators" in evals and isinstance(evals["evaluators"], list):
                        evaluator_count = len(evals["evaluators"])

                evaluations_data = {
                    "dataset_count": dataset_count,
                    "evaluator_count": evaluator_count,
                    "runs": evals.get("runs", 1) if isinstance(evals, dict) else 1,
                    "parallel": evals.get("parallel", False) if isinstance(evals, dict) else False,
                }

            # Build metadata response
            metadata = {
                "description": registry.description,
                "input": registry.input_schema if registry.input_schema else {},
                "output": registry.output_schema if registry.output_schema else {},
                "agents": {
                    name: {
                        "name": agent.name,
                        "provider": agent.provider,
                        "model": agent.model if isinstance(agent.model, str) else str(agent.model),
                        "system_prompt": (
                            agent.system_prompt
                            if isinstance(agent.system_prompt, str)
                            else "[Dynamic Prompt]"
                        ),
                        "tools": agent.tools,
                    }
                    for name, agent in registry.agents.items()
                },
                "toolsets": {name: toolset for name, toolset in registry.toolsets.items()},
                "tools": sorted(list(all_tools)),
                "specifications": specifications_data,
                "evaluations": evaluations_data,
            }

            return jsonify({"success": True, "metadata": metadata})

        except Exception as e:
            logger.error("Error extracting procedure metadata: %s", e, exc_info=True)
            return jsonify({"error": str(e)}), 500

    @app.route("/api/validate", methods=["POST"])
    def validate_procedure():
        """Validate Tactus procedure code."""
        data = request.json
        content = data.get("content")

        if content is None:
            return jsonify({"error": "Missing 'content' parameter"}), 400

        try:
            validator = TactusValidator()
            result = validator.validate(content)

            return jsonify(
                {
                    "valid": result.valid,
                    "errors": [
                        {
                            "message": err.message,
                            "line": err.location[0] if err.location else None,
                            "column": err.location[1] if err.location else None,
                            "level": err.level,
                        }
                        for err in result.errors
                    ],
                    "warnings": [
                        {
                            "message": warn.message,
                            "line": warn.location[0] if warn.location else None,
                            "column": warn.location[1] if warn.location else None,
                            "level": warn.level,
                        }
                        for warn in result.warnings
                    ],
                }
            )
        except Exception as e:
            logger.error("Error validating code: %s", e)
            return jsonify({"error": str(e)}), 500

    @app.route("/api/validate/stream", methods=["GET"])
    def validate_stream():
        """Validate Tactus code with SSE streaming output."""
        file_path = request.args.get("path")

        if not file_path:
            return jsonify({"error": "Missing 'path' parameter"}), 400

        try:
            # Resolve path within workspace
            path = _resolve_workspace_path(file_path)

            # Ensure file exists
            if not path.exists():
                return jsonify({"error": f"File not found: {file_path}"}), 404

            def generate_events():
                """Generator function that yields SSE validation events."""
                try:
                    import json
                    from datetime import datetime

                    # Read and validate file
                    content = path.read_text()
                    validator = TactusValidator()
                    result = validator.validate(content)

                    # Emit validation event
                    validation_event = {
                        "event_type": "validation",
                        "valid": result.valid,
                        "errors": [
                            {
                                "message": err.message,
                                "line": err.location[0] if err.location else None,
                                "column": err.location[1] if err.location else None,
                                "level": err.level,
                            }
                            for err in result.errors
                        ],
                        "warnings": [
                            {
                                "message": warn.message,
                                "line": warn.location[0] if warn.location else None,
                                "column": warn.location[1] if warn.location else None,
                                "level": warn.level,
                            }
                            for warn in result.warnings
                        ],
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                    }
                    yield f"data: {json.dumps(validation_event)}\n\n"

                except Exception as e:
                    logger.error("Error in validation: %s", e, exc_info=True)
                    error_event = {
                        "event_type": "execution",
                        "lifecycle_stage": "error",
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "details": {"error": str(e)},
                    }
                    yield f"data: {json.dumps(error_event)}\n\n"

            return Response(
                stream_with_context(generate_events()),
                mimetype="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                    "Connection": "keep-alive",
                },
            )

        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            logger.error("Error setting up validation: %s", e, exc_info=True)
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
                cwd=WORKSPACE_ROOT,
            )

            return jsonify(
                {
                    "success": result.returncode == 0,
                    "exitCode": result.returncode,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                }
            )
        except subprocess.TimeoutExpired:
            return jsonify({"error": "Procedure execution timed out (30s)"}), 408
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            logger.error("Error running procedure %s: %s", file_path, e)
            return jsonify({"error": str(e)}), 500

    @app.route("/api/run/stream", methods=["GET", "POST"])
    def run_procedure_stream():
        """
        Run a Tactus procedure with SSE streaming output.

        For GET:
        - path: workspace-relative path to procedure file (required, query param)
        - inputs: JSON-encoded input parameters (optional, query param)

        For POST:
        - path: workspace-relative path to procedure file (required, JSON body)
        - content: optional file content to save before running (JSON body)
        - inputs: input parameters as object (optional, JSON body)
        """
        if request.method == "POST":
            data = request.json or {}
            file_path = data.get("path")
            content = data.get("content")
            inputs = data.get("inputs", {})
        else:
            file_path = request.args.get("path")
            content = None
            inputs_json = request.args.get("inputs", "{}")
            # Parse inputs JSON for GET
            try:
                inputs = json.loads(inputs_json) if inputs_json else {}
            except json.JSONDecodeError as e:
                return jsonify({"error": f"Invalid 'inputs' JSON: {e}"}), 400

        if not file_path:
            return jsonify({"error": "Missing 'path' parameter"}), 400

        try:
            # Resolve path within workspace
            path = _resolve_workspace_path(file_path)

            # Save content if provided (POST requests can include file content)
            if content is not None:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)

            # Ensure file exists
            if not path.exists():
                return jsonify({"error": f"File not found: {file_path}"}), 404

            procedure_id = f"ide-{path.stem}"

            def generate_events():
                """Generator function that yields SSE events."""
                log_handler = None
                all_events = []  # Collect all events to save at the end
                try:
                    # Send start event
                    import json
                    from datetime import datetime
                    from tactus.adapters.ide_log import IDELogHandler
                    from tactus.core.runtime import TactusRuntime
                    from tactus.adapters.file_storage import FileStorage
                    from nanoid import generate

                    # Generate unique run_id for this execution
                    run_id = generate(size=21)

                    start_event = {
                        "event_type": "execution",
                        "lifecycle_stage": "start",
                        "procedure_id": procedure_id,
                        "run_id": run_id,
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "details": {"path": file_path},
                        "inputs": inputs,  # Include inputs in start event
                    }
                    all_events.append(start_event)
                    yield f"data: {json.dumps(start_event)}\n\n"

                    # Create IDE log handler to collect structured events
                    log_handler = IDELogHandler()

                    # Create storage backend
                    from pathlib import Path as PathLib

                    storage_dir = (
                        str(PathLib(WORKSPACE_ROOT) / ".tac" / "storage")
                        if WORKSPACE_ROOT
                        else "~/.tactus/storage"
                    )
                    storage_backend = FileStorage(storage_dir=storage_dir)

                    # Load configuration cascade for this procedure
                    from tactus.core.config_manager import ConfigManager

                    config_manager = ConfigManager()
                    merged_config = config_manager.load_cascade(path)

                    # Extract API keys and other config values
                    openai_api_key = (
                        merged_config.get("openai", {}).get("api_key")
                        if isinstance(merged_config.get("openai"), dict)
                        else merged_config.get("openai_api_key")
                    ) or os.environ.get("OPENAI_API_KEY")

                    tool_paths = merged_config.get("tool_paths")
                    mcp_servers = merged_config.get("mcp_servers", {})

                    # Create HITL handler with SSE channel for IDE integration
                    from tactus.adapters.control_loop import (
                        ControlLoopHandler,
                        ControlLoopHITLAdapter,
                    )
                    from tactus.adapters.channels import load_default_channels

                    # Load default channels (CLI + IPC) and add SSE channel
                    channels = load_default_channels(procedure_id=procedure_id)
                    sse_channel = get_sse_channel()

                    # Add SSE channel to the list
                    channels.append(sse_channel)

                    # Create control loop handler with all channels
                    control_handler = ControlLoopHandler(
                        channels=channels,
                        storage=storage_backend,
                    )

                    # Wrap in adapter for backward compatibility
                    hitl_handler = ControlLoopHITLAdapter(control_handler)

                    # Create runtime with log handler, run_id, and loaded config
                    runtime = TactusRuntime(
                        procedure_id=procedure_id,
                        storage_backend=storage_backend,
                        hitl_handler=hitl_handler,  # Now includes SSE channel!
                        log_handler=log_handler,
                        run_id=run_id,
                        source_file_path=str(path),
                        openai_api_key=openai_api_key,
                        tool_paths=tool_paths,
                        mcp_servers=mcp_servers,
                        external_config=merged_config,
                    )

                    # Read procedure source
                    source = path.read_text()

                    # Check Docker availability for sandbox execution
                    from tactus.sandbox import is_docker_available, SandboxConfig, ContainerRunner

                    docker_available, docker_reason = is_docker_available()
                    # Enable dev_mode by default in IDE for live code mounting
                    sandbox_config = SandboxConfig(dev_mode=True)
                    use_sandbox = docker_available and not sandbox_config.is_explicitly_disabled()

                    if use_sandbox:
                        logger.info("[SANDBOX] Docker available, using container execution")
                    else:
                        logger.info(
                            "[SANDBOX] Direct execution (Docker: %s, reason: %s)",
                            docker_available,
                            docker_reason,
                        )

                    # Create event queue for sandbox event streaming (if using sandbox)
                    sandbox_event_queue = None
                    if use_sandbox:
                        sandbox_event_queue = queue.Queue()

                        # Emit container starting event
                        container_starting_event = {
                            "event_type": "container_status",
                            "status": "starting",
                            "execution_id": run_id,
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                        }
                        all_events.append(container_starting_event)
                        yield f"data: {json.dumps(container_starting_event)}\n\n"

                    # Run in a thread to avoid blocking
                    import asyncio

                    result_container = {
                        "result": None,
                        "error": None,
                        "done": False,
                        "container_ready": False,
                    }

                    # Capture inputs in closure scope for the thread
                    procedure_inputs = inputs

                    async def handle_container_control_request(request_data: dict) -> dict:
                        """
                        Bridge container HITL requests to host's SSE channel.

                        This handler is called by the broker when the container sends
                        a control.request. It forwards the request to the SSE channel,
                        waits for the user response in the IDE, and returns the response
                        data back to the container.
                        """
                        import threading
                        from tactus.protocols.control import ControlRequest

                        # Parse the request
                        request = ControlRequest.model_validate(request_data)
                        logger.info(
                            "[HITL] Container control request %s for procedure %s",
                            request.request_id,
                            request.procedure_id,
                        )

                        # Get SSE channel
                        sse_channel = get_sse_channel()

                        # Create a threading event to wait for response
                        response_event = threading.Event()
                        response_data = {}

                        # Register pending request
                        _pending_hitl_requests[request.request_id] = {
                            "event": response_event,
                            "response": response_data,
                        }

                        try:
                            # Send to SSE channel (delivers to IDE UI)
                            delivery = await sse_channel.send(request)
                            if not delivery.success:
                                raise RuntimeError(
                                    f"Failed to deliver HITL request to IDE: {delivery.error_message}"
                                )

                            logger.info(
                                "[HITL] Request %s delivered to IDE, waiting for response...",
                                request.request_id,
                            )

                            # Wait for response (with timeout) - run blocking wait in thread pool
                            timeout_seconds = request.timeout_seconds or 300  # 5 min default
                            logger.info(
                                "[HITL] Starting wait for response (timeout=%ss)...",
                                timeout_seconds,
                            )
                            result = await asyncio.to_thread(
                                response_event.wait, timeout=timeout_seconds
                            )
                            logger.info("[HITL] Wait completed, result=%s", result)

                            if result:
                                logger.info(
                                    "[HITL] Received response for %s: %s",
                                    request.request_id,
                                    response_data.get("value"),
                                )
                                return response_data
                            else:
                                # Timeout
                                logger.warning("[HITL] Timeout for %s", request.request_id)
                                return {
                                    "value": request.default_value,
                                    "timed_out": True,
                                    "channel_id": "sse",
                                }
                        finally:
                            # Clean up pending request
                            _pending_hitl_requests.pop(request.request_id, None)

                    def run_procedure():
                        try:
                            # Create new event loop for this thread
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)

                            if use_sandbox:
                                # Use sandbox execution (events streamed via broker over UDS)
                                runner = ContainerRunner(sandbox_config)

                                # Pass async control handler directly (broker calls it in async context)
                                # Build LLM backend config (provider-agnostic)
                                llm_backend_config = {}
                                if openai_api_key:
                                    llm_backend_config["openai_api_key"] = openai_api_key

                                exec_result = loop.run_until_complete(
                                    runner.run(
                                        source=source,
                                        params=procedure_inputs,
                                        source_file_path=str(path),
                                        format="lua",
                                        event_handler=(
                                            sandbox_event_queue.put if sandbox_event_queue else None
                                        ),
                                        run_id=run_id,
                                        control_handler=handle_container_control_request,
                                        llm_backend_config=llm_backend_config,
                                    )
                                )

                                # Mark container as ready after first response
                                result_container["container_ready"] = True

                                # Extract result from ExecutionResult
                                if exec_result.status.value == "success":
                                    result_container["result"] = exec_result.result
                                else:
                                    raise Exception(exec_result.error or "Sandbox execution failed")
                            else:
                                # Direct execution (no sandbox)
                                result = loop.run_until_complete(
                                    runtime.execute(source, context=procedure_inputs, format="lua")
                                )
                                result_container["result"] = result
                        except Exception as e:
                            result_container["error"] = e
                        finally:
                            result_container["done"] = True
                            loop.close()

                    exec_thread = threading.Thread(target=run_procedure)
                    exec_thread.daemon = True
                    exec_thread.start()

                    # Emit container running event after starting
                    if use_sandbox:
                        container_running_event = {
                            "event_type": "container_status",
                            "status": "running",
                            "execution_id": run_id,
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                        }
                        all_events.append(container_running_event)
                        yield f"data: {json.dumps(container_running_event)}\n\n"

                    # Stream events based on execution mode
                    # Poll aggressively to stream events in real-time
                    while not result_container["done"]:
                        events_sent = False

                        if use_sandbox and sandbox_event_queue:
                            # Stream from sandbox callback queue
                            try:
                                event_dict = sandbox_event_queue.get(timeout=0.01)
                                all_events.append(event_dict)
                                yield f"data: {json.dumps(event_dict)}\n\n"
                                events_sent = True
                            except queue.Empty:
                                pass

                            # Also check for HITL events from SSE channel (container HITL)
                            hitl_event = sse_channel.get_next_event(timeout=0.001)
                            if hitl_event:
                                all_events.append(hitl_event)
                                yield f"data: {json.dumps(hitl_event)}\n\n"
                                events_sent = True
                        else:
                            # Stream from IDELogHandler (direct execution)
                            # Get one event at a time to stream immediately
                            try:
                                event = log_handler.events.get(timeout=0.001)
                                try:
                                    # Serialize with ISO format for datetime
                                    event_dict = event.model_dump(mode="json")
                                    # Format timestamp: add 'Z' only if no timezone info present
                                    iso_string = event.timestamp.isoformat()
                                    if not (
                                        iso_string.endswith("Z")
                                        or "+" in iso_string
                                        or iso_string.count("-") > 2
                                    ):
                                        iso_string += "Z"
                                    event_dict["timestamp"] = iso_string
                                    all_events.append(event_dict)
                                    yield f"data: {json.dumps(event_dict)}\n\n"
                                    events_sent = True
                                except Exception as e:
                                    logger.error(
                                        "Error serializing event: %s",
                                        e,
                                        exc_info=True,
                                    )
                                    logger.error(
                                        "Event type: %s, Event: %s",
                                        type(event),
                                        event,
                                    )
                            except queue.Empty:
                                pass

                            # Also check for HITL events from SSE channel
                            hitl_event = sse_channel.get_next_event(timeout=0.001)
                            if hitl_event:
                                all_events.append(hitl_event)
                                yield f"data: {json.dumps(hitl_event)}\n\n"
                                events_sent = True

                        # Only sleep if no events were sent to maintain responsiveness
                        if not events_sent:
                            time.sleep(0.01)

                    # Get any remaining events
                    if use_sandbox and sandbox_event_queue:
                        # Drain sandbox event queue with retries to catch late-arriving events
                        # Agent streaming events and ExecutionSummaryEvent may still be in flight
                        max_wait = 2.0  # Wait up to 2 seconds for final events
                        poll_interval = 0.05  # Poll every 50ms
                        elapsed = 0.0
                        consecutive_empty = 0
                        max_consecutive_empty = 4  # Stop after 4 empty polls (200ms of no events)

                        while elapsed < max_wait and consecutive_empty < max_consecutive_empty:
                            try:
                                event_dict = sandbox_event_queue.get(timeout=poll_interval)
                                all_events.append(event_dict)
                                yield f"data: {json.dumps(event_dict)}\n\n"
                                consecutive_empty = 0  # Reset counter when we get an event
                            except queue.Empty:
                                consecutive_empty += 1
                                elapsed += poll_interval

                        # Emit container stopped event
                        container_stopped_event = {
                            "event_type": "container_status",
                            "status": "stopped",
                            "execution_id": run_id,
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                        }
                        all_events.append(container_stopped_event)
                        yield f"data: {json.dumps(container_stopped_event)}\n\n"
                    else:
                        # Drain IDELogHandler events (direct execution)
                        events = log_handler.get_events(timeout=0.1)
                        for event in events:
                            try:
                                # Serialize with ISO format for datetime
                                event_dict = event.model_dump(mode="json")
                                # Format timestamp: add 'Z' only if no timezone info present
                                iso_string = event.timestamp.isoformat()
                                if not (
                                    iso_string.endswith("Z")
                                    or "+" in iso_string
                                    or iso_string.count("-") > 2
                                ):
                                    iso_string += "Z"
                                event_dict["timestamp"] = iso_string
                                all_events.append(event_dict)
                                yield f"data: {json.dumps(event_dict)}\n\n"
                            except Exception as e:
                                logger.error(
                                    "Error serializing event: %s",
                                    e,
                                    exc_info=True,
                                )
                                logger.error(
                                    "Event type: %s, Event: %s",
                                    type(event),
                                    event,
                                )

                    # Wait for thread to finish
                    exec_thread.join(timeout=1)

                    # Send completion event
                    if result_container["error"]:
                        complete_event = {
                            "event_type": "execution",
                            "lifecycle_stage": "error",
                            "procedure_id": procedure_id,
                            "exit_code": 1,
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "details": {"success": False, "error": str(result_container["error"])},
                        }
                    else:
                        complete_event = {
                            "event_type": "execution",
                            "lifecycle_stage": "complete",
                            "procedure_id": procedure_id,
                            "exit_code": 0,
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "details": {"success": True},
                        }
                    all_events.append(complete_event)
                    yield f"data: {json.dumps(complete_event)}\n\n"

                    # Consolidate streaming chunks before saving to disk
                    # Keep only the final accumulated text for each agent
                    consolidated_events = []
                    stream_chunks_by_agent = {}

                    for event in all_events:
                        if event.get("event_type") == "agent_stream_chunk":
                            # Track by agent name, keeping only the latest
                            agent_name = event.get("agent_name")
                            stream_chunks_by_agent[agent_name] = event
                        else:
                            consolidated_events.append(event)

                    # Add the final consolidated chunks
                    consolidated_events.extend(stream_chunks_by_agent.values())

                    # Save consolidated events to disk
                    try:
                        from pathlib import Path as PathLib

                        events_dir = PathLib(storage_dir) / "events"
                        events_dir.mkdir(parents=True, exist_ok=True)
                        events_file = events_dir / f"{run_id}.json"
                        with open(events_file, "w") as f:
                            json.dump(consolidated_events, f, indent=2)
                    except Exception as e:
                        logger.error(
                            "Failed to save events for run %s: %s",
                            run_id,
                            e,
                            exc_info=True,
                        )

                except Exception as e:
                    logger.error("Error in streaming execution: %s", e, exc_info=True)
                    error_event = {
                        "event_type": "execution",
                        "lifecycle_stage": "error",
                        "procedure_id": procedure_id,
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "details": {"error": str(e)},
                    }
                    yield f"data: {json.dumps(error_event)}\n\n"

            return Response(
                stream_with_context(generate_events()),
                mimetype="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                    "Connection": "keep-alive",
                },
            )

        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            logger.error("Error setting up streaming execution: %s", e, exc_info=True)
            return jsonify({"error": str(e)}), 500

    @app.route("/api/test/stream", methods=["GET"])
    def test_procedure_stream():
        """
        Run BDD tests with SSE streaming output.

        Query params:
        - path: procedure file path (required)
        - mock: use mock mode (optional, default true)
        - scenario: specific scenario name (optional)
        - parallel: run in parallel (optional, default false)
        """
        file_path = request.args.get("path")

        if not file_path:
            return jsonify({"error": "Missing 'path' parameter"}), 400

        # Get options
        mock = request.args.get("mock", "true").lower() == "true"
        parallel = request.args.get("parallel", "false").lower() == "true"

        try:
            # Resolve path within workspace
            path = _resolve_workspace_path(file_path)

            # Ensure file exists
            if not path.exists():
                return jsonify({"error": f"File not found: {file_path}"}), 404

            procedure_id = path.stem

            def generate_events():
                """Generator function that yields SSE test events."""
                try:
                    import json
                    from datetime import datetime
                    from tactus.validation import TactusValidator
                    from tactus.testing import TactusTestRunner, GherkinParser

                    # Validate and extract specifications
                    validator = TactusValidator()
                    validation_result = validator.validate_file(str(path))

                    if not validation_result.valid:
                        # Emit validation error
                        error_event = {
                            "event_type": "execution",
                            "lifecycle_stage": "error",
                            "procedure_id": procedure_id,
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "details": {
                                "error": "Validation failed",
                                "errors": [
                                    {"message": e.message, "level": e.level}
                                    for e in validation_result.errors
                                ],
                            },
                        }
                        yield f"data: {json.dumps(error_event)}\n\n"
                        return

                    if (
                        not validation_result.registry
                        or not validation_result.registry.gherkin_specifications
                    ):
                        # No specifications found
                        error_event = {
                            "event_type": "execution",
                            "lifecycle_stage": "error",
                            "procedure_id": procedure_id,
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "details": {"error": "No specifications found in procedure"},
                        }
                        yield f"data: {json.dumps(error_event)}\n\n"
                        return

                    # Clear Behave's global step registry before each test run
                    # This prevents conflicts when running multiple tests in the same Flask process
                    try:
                        from behave import step_registry

                        # Clear all registered steps (each step_type maps to a list)
                        step_registry.registry.steps = {
                            "given": [],
                            "when": [],
                            "then": [],
                            "step": [],
                        }
                        # Recreate the decorators
                        from behave.step_registry import setup_step_decorators

                        setup_step_decorators()
                    except Exception as e:
                        logger.warning("Could not reset Behave step registry: %s", e)

                    # Setup test runner with mocks from registry
                    mock_tools = None
                    if mock:
                        # Start with default done mock
                        mock_tools = {"done": {"status": "ok"}}
                        # Add tool mocks from Mocks {} block in .tac file
                        if validation_result.registry.mocks:
                            for tool_name, mock_config in validation_result.registry.mocks.items():
                                # Extract output/response from mock config
                                if isinstance(mock_config, dict) and "output" in mock_config:
                                    mock_tools[tool_name] = mock_config["output"]
                                else:
                                    mock_tools[tool_name] = mock_config
                    runner = TactusTestRunner(path, mock_tools=mock_tools, mocked=mock)
                    runner.setup(validation_result.registry.gherkin_specifications)

                    # Get parsed feature to count scenarios
                    parser = GherkinParser()
                    parsed_feature = parser.parse(validation_result.registry.gherkin_specifications)
                    total_scenarios = len(parsed_feature.scenarios)

                    # Emit started event
                    start_event = {
                        "event_type": "test_started",
                        "procedure_file": str(path),
                        "total_scenarios": total_scenarios,
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                    }
                    yield f"data: {json.dumps(start_event)}\n\n"

                    # Run tests
                    test_result = runner.run_tests(parallel=parallel)

                    # Emit scenario completion events
                    for feature in test_result.features:
                        for scenario in feature.scenarios:
                            scenario_event = {
                                "event_type": "test_scenario_completed",
                                "scenario_name": scenario.name,
                                "status": scenario.status,
                                "duration": scenario.duration,
                                "total_cost": scenario.total_cost,
                                "total_tokens": scenario.total_tokens,
                                "llm_calls": scenario.llm_calls,
                                "iterations": scenario.iterations,
                                "tools_used": scenario.tools_used,
                                "timestamp": datetime.utcnow().isoformat() + "Z",
                            }
                            yield f"data: {json.dumps(scenario_event)}\n\n"

                    # Emit completed event
                    complete_event = {
                        "event_type": "test_completed",
                        "result": {
                            "total_scenarios": test_result.total_scenarios,
                            "passed_scenarios": test_result.passed_scenarios,
                            "failed_scenarios": test_result.failed_scenarios,
                            "total_cost": test_result.total_cost,
                            "total_tokens": test_result.total_tokens,
                            "total_llm_calls": test_result.total_llm_calls,
                            "total_iterations": test_result.total_iterations,
                            "unique_tools_used": test_result.unique_tools_used,
                            "features": [
                                {
                                    "name": f.name,
                                    "scenarios": [
                                        {
                                            "name": s.name,
                                            "status": s.status,
                                            "duration": s.duration,
                                            "steps": [
                                                {
                                                    "keyword": step.keyword,
                                                    "text": step.message,
                                                    "status": step.status,
                                                    "error_message": step.error_message,
                                                }
                                                for step in s.steps
                                            ],
                                        }
                                        for s in f.scenarios
                                    ],
                                }
                                for f in test_result.features
                            ],
                        },
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                    }
                    yield f"data: {json.dumps(complete_event)}\n\n"

                    # Cleanup
                    runner.cleanup()

                except Exception as e:
                    logger.error("Error in test execution: %s", e, exc_info=True)
                    error_event = {
                        "event_type": "execution",
                        "lifecycle_stage": "error",
                        "procedure_id": procedure_id,
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "details": {"error": str(e)},
                    }
                    yield f"data: {json.dumps(error_event)}\n\n"

            return Response(
                stream_with_context(generate_events()),
                mimetype="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                    "Connection": "keep-alive",
                },
            )

        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            logger.error("Error setting up test execution: %s", e, exc_info=True)
            return jsonify({"error": str(e)}), 500

    @app.route("/api/evaluate/stream", methods=["GET"])
    def evaluate_procedure_stream():
        """
        Run BDD evaluation with SSE streaming output.

        Query params:
        - path: procedure file path (required)
        - runs: number of runs per scenario (optional, default 10)
        - mock: use mock mode (optional, default true)
        - scenario: specific scenario name (optional)
        - parallel: run in parallel (optional, default true)
        """
        file_path = request.args.get("path")

        if not file_path:
            return jsonify({"error": "Missing 'path' parameter"}), 400

        # Get options
        runs = int(request.args.get("runs", "10"))
        mock = request.args.get("mock", "true").lower() == "true"
        parallel = request.args.get("parallel", "true").lower() == "true"

        try:
            # Resolve path within workspace
            path = _resolve_workspace_path(file_path)

            # Ensure file exists
            if not path.exists():
                return jsonify({"error": f"File not found: {file_path}"}), 404

            procedure_id = path.stem

            def generate_events():
                """Generator function that yields SSE evaluation events."""
                try:
                    import json
                    from datetime import datetime
                    from tactus.validation import TactusValidator
                    from tactus.testing import TactusEvaluationRunner, GherkinParser

                    # Validate and extract specifications
                    validator = TactusValidator()
                    validation_result = validator.validate_file(str(path))

                    if not validation_result.valid:
                        error_event = {
                            "event_type": "execution",
                            "lifecycle_stage": "error",
                            "procedure_id": procedure_id,
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "details": {
                                "error": "Validation failed",
                                "errors": [
                                    {"message": e.message, "level": e.level}
                                    for e in validation_result.errors
                                ],
                            },
                        }
                        yield f"data: {json.dumps(error_event)}\n\n"
                        return

                    if (
                        not validation_result.registry
                        or not validation_result.registry.gherkin_specifications
                    ):
                        error_event = {
                            "event_type": "execution",
                            "lifecycle_stage": "error",
                            "procedure_id": procedure_id,
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "details": {"error": "No specifications found in procedure"},
                        }
                        yield f"data: {json.dumps(error_event)}\n\n"
                        return

                    # Setup evaluation runner
                    mock_tools = {"done": {"status": "ok"}} if mock else None
                    evaluator = TactusEvaluationRunner(path, mock_tools=mock_tools)
                    evaluator.setup(validation_result.registry.gherkin_specifications)

                    # Get parsed feature to count scenarios
                    parser = GherkinParser()
                    parsed_feature = parser.parse(validation_result.registry.gherkin_specifications)
                    total_scenarios = len(parsed_feature.scenarios)

                    # Emit started event
                    start_event = {
                        "event_type": "evaluation_started",
                        "procedure_file": str(path),
                        "total_scenarios": total_scenarios,
                        "runs_per_scenario": runs,
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                    }
                    yield f"data: {json.dumps(start_event)}\n\n"

                    # Run evaluation
                    eval_results = evaluator.evaluate_all(runs=runs, parallel=parallel)

                    # Emit progress/completion events for each scenario
                    for eval_result in eval_results:
                        progress_event = {
                            "event_type": "evaluation_progress",
                            "scenario_name": eval_result.scenario_name,
                            "completed_runs": eval_result.total_runs,
                            "total_runs": eval_result.total_runs,
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                        }
                        yield f"data: {json.dumps(progress_event)}\n\n"

                    # Emit completed event
                    complete_event = {
                        "event_type": "evaluation_completed",
                        "results": [
                            {
                                "scenario_name": r.scenario_name,
                                "total_runs": r.total_runs,
                                "successful_runs": r.successful_runs,
                                "failed_runs": r.failed_runs,
                                "success_rate": r.success_rate,
                                "consistency_score": r.consistency_score,
                                "is_flaky": r.is_flaky,
                                "avg_duration": r.avg_duration,
                                "std_duration": r.std_duration,
                            }
                            for r in eval_results
                        ],
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                    }
                    yield f"data: {json.dumps(complete_event)}\n\n"

                    # Cleanup
                    evaluator.cleanup()

                except Exception as e:
                    logger.error("Error in evaluation execution: %s", e, exc_info=True)
                    error_event = {
                        "event_type": "execution",
                        "lifecycle_stage": "error",
                        "procedure_id": procedure_id,
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "details": {"error": str(e)},
                    }
                    yield f"data: {json.dumps(error_event)}\n\n"

            return Response(
                stream_with_context(generate_events()),
                mimetype="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                    "Connection": "keep-alive",
                },
            )

        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            logger.error("Error setting up evaluation execution: %s", e, exc_info=True)
            return jsonify({"error": str(e)}), 500

    @app.route("/api/pydantic-eval/stream", methods=["GET"])
    def pydantic_eval_stream():
        """
        Run Pydantic Evals with SSE streaming output.

        Query params:
        - path: procedure file path (required)
        - runs: number of runs per case (optional, default 1)
        """
        logger.info("Pydantic eval stream request: args=%s", request.args)

        file_path = request.args.get("path")
        if not file_path:
            logger.error("Missing 'path' parameter")
            return jsonify({"error": "Missing 'path' parameter"}), 400

        runs = int(request.args.get("runs", "1"))

        try:
            # Resolve path within workspace
            logger.info("Resolving path: %s", file_path)
            path = _resolve_workspace_path(file_path)
            logger.info("Resolved to: %s", path)

            if not path.exists():
                return jsonify({"error": f"File not found: {file_path}"}), 404

            procedure_id = path.stem

            def generate_events():
                """Generator function that yields SSE evaluation events."""
                try:
                    from tactus.testing.pydantic_eval_runner import TactusPydanticEvalRunner
                    from tactus.testing.eval_models import (
                        EvaluationConfig,
                        EvalCase,
                        EvaluatorConfig,
                    )

                    # Validate and extract evaluations
                    validator = TactusValidator()
                    validation_result = validator.validate_file(str(path))

                    if not validation_result.valid:
                        error_event = {
                            "event_type": "execution",
                            "lifecycle_stage": "error",
                            "procedure_id": procedure_id,
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "details": {
                                "error": "Validation failed",
                                "errors": [e.message for e in validation_result.errors],
                            },
                        }
                        yield f"data: {json.dumps(error_event)}\n\n"
                        return

                    if (
                        not validation_result.registry
                        or not validation_result.registry.pydantic_evaluations
                    ):
                        error_event = {
                            "event_type": "execution",
                            "lifecycle_stage": "error",
                            "procedure_id": procedure_id,
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "details": {"error": "No evaluations found in procedure"},
                        }
                        yield f"data: {json.dumps(error_event)}\n\n"
                        return

                    # Parse evaluation config FIRST (before start event)
                    eval_dict = validation_result.registry.pydantic_evaluations
                    dataset_cases = [EvalCase(**c) for c in eval_dict.get("dataset", [])]
                    evaluators = [EvaluatorConfig(**e) for e in eval_dict.get("evaluators", [])]

                    # Parse thresholds if present
                    from tactus.testing.eval_models import EvaluationThresholds

                    thresholds = None
                    if "thresholds" in eval_dict:
                        thresholds = EvaluationThresholds(**eval_dict["thresholds"])

                    # Use runs from file if specified, otherwise use query param
                    actual_runs = eval_dict.get("runs", runs)

                    # Emit start event (after actual_runs is defined)
                    start_event = {
                        "event_type": "execution",
                        "lifecycle_stage": "started",
                        "procedure_id": procedure_id,
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "details": {"type": "pydantic_eval", "runs": actual_runs},
                    }
                    yield f"data: {json.dumps(start_event)}\n\n"

                    eval_config = EvaluationConfig(
                        dataset=dataset_cases,
                        evaluators=evaluators,
                        runs=actual_runs,
                        parallel=False,  # Sequential for IDE streaming
                        thresholds=thresholds,
                    )

                    # Run evaluation
                    runner = TactusPydanticEvalRunner(
                        procedure_file=path,
                        eval_config=eval_config,
                        openai_api_key=os.environ.get("OPENAI_API_KEY"),
                    )

                    report = runner.run_evaluation()

                    # Emit results
                    result_details = {
                        "type": "pydantic_eval",
                        "total_cases": len(report.cases) if hasattr(report, "cases") else 0,
                    }

                    if hasattr(report, "cases"):
                        result_details["cases"] = []
                        for case in report.cases:
                            # Convert case to dict, handling non-serializable objects
                            def make_serializable(obj):
                                """Recursively convert objects to JSON-serializable types."""
                                if isinstance(obj, (str, int, float, bool, type(None))):
                                    return obj
                                elif isinstance(obj, dict):
                                    return {k: make_serializable(v) for k, v in obj.items()}
                                elif isinstance(obj, (list, tuple)):
                                    return [make_serializable(item) for item in obj]
                                elif hasattr(obj, "__dict__"):
                                    # Convert object with __dict__ to dict
                                    return {
                                        k: make_serializable(v)
                                        for k, v in obj.__dict__.items()
                                        if not k.startswith("_")
                                    }
                                else:
                                    return str(obj)

                            case_dict = {
                                "name": str(case.name),
                                "inputs": make_serializable(case.inputs),
                                "output": make_serializable(case.output),
                                "assertions": make_serializable(case.assertions),
                                "scores": make_serializable(case.scores),
                                "labels": make_serializable(case.labels),
                                "duration": (
                                    float(case.task_duration)
                                    if hasattr(case, "task_duration")
                                    else 0.0
                                ),
                            }
                            result_details["cases"].append(case_dict)

                    # Check thresholds
                    passed, violations = runner.check_thresholds(report)
                    result_details["thresholds_passed"] = passed
                    if violations:
                        result_details["threshold_violations"] = violations

                    result_event = {
                        "event_type": "execution",
                        "lifecycle_stage": "complete",
                        "procedure_id": procedure_id,
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "details": result_details,
                    }
                    yield f"data: {json.dumps(result_event)}\n\n"

                except ImportError as e:
                    error_event = {
                        "event_type": "execution",
                        "lifecycle_stage": "error",
                        "procedure_id": procedure_id,
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "details": {"error": f"pydantic_evals not installed: {e}"},
                    }
                    yield f"data: {json.dumps(error_event)}\n\n"
                except Exception as e:
                    logger.error("Error running Pydantic Evals: %s", e, exc_info=True)
                    error_event = {
                        "event_type": "execution",
                        "lifecycle_stage": "error",
                        "procedure_id": procedure_id,
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "details": {"error": str(e)},
                    }
                    yield f"data: {json.dumps(error_event)}\n\n"

            return Response(
                stream_with_context(generate_events()),
                mimetype="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                    "Connection": "keep-alive",
                },
            )

        except Exception as e:
            logger.error("Error setting up Pydantic Evals: %s", e, exc_info=True)
            return jsonify({"error": str(e)}), 500

    @app.route("/api/traces/runs", methods=["GET"])
    def list_trace_runs():
        """List all execution runs by grouping checkpoints by run_id."""
        try:
            from pathlib import Path as PathLib
            from tactus.adapters.file_storage import FileStorage
            from collections import defaultdict

            # Get optional query params
            procedure = request.args.get("procedure")
            limit = int(request.args.get("limit", "50"))

            # Create storage backend
            storage_dir = (
                str(PathLib(WORKSPACE_ROOT) / ".tac" / "storage")
                if WORKSPACE_ROOT
                else "~/.tactus/storage"
            )
            storage_backend = FileStorage(storage_dir=storage_dir)

            # Load procedure metadata
            if not procedure:
                return jsonify({"runs": []})

            metadata = storage_backend.load_procedure_metadata(procedure)

            # Group checkpoints by run_id
            runs_dict = defaultdict(list)
            for checkpoint in metadata.execution_log:
                runs_dict[checkpoint.run_id].append(checkpoint)

            # Build runs list
            runs_data = []
            for run_id, checkpoints in runs_dict.items():
                # Sort checkpoints by position
                checkpoints.sort(key=lambda c: c.position)

                # Get start/end times
                start_time = checkpoints[0].timestamp if checkpoints else None
                end_time = checkpoints[-1].timestamp if checkpoints else None

                runs_data.append(
                    {
                        "run_id": run_id,
                        "procedure_name": procedure,
                        "start_time": start_time.isoformat() if start_time else None,
                        "end_time": end_time.isoformat() if end_time else None,
                        "status": "COMPLETED",  # Can be enhanced later
                        "checkpoint_count": len(checkpoints),
                    }
                )

            # Sort by start_time (most recent first)
            runs_data.sort(key=lambda r: r["start_time"] or "", reverse=True)

            # Apply limit
            runs_data = runs_data[:limit]

            return jsonify({"runs": runs_data})
        except Exception as e:
            logger.error("Error listing trace runs: %s", e, exc_info=True)
            return jsonify({"error": str(e)}), 500

    @app.route("/api/traces/runs/<run_id>", methods=["GET"])
    def get_trace_run(run_id: str):
        """Get a specific execution run by filtering checkpoints by run_id."""
        try:
            from pathlib import Path as PathLib
            from tactus.adapters.file_storage import FileStorage

            # Get procedure name from query param or try to find it
            procedure = request.args.get("procedure")
            if not procedure:
                return jsonify({"error": "procedure parameter required"}), 400

            # Create storage backend
            storage_dir = (
                str(PathLib(WORKSPACE_ROOT) / ".tac" / "storage")
                if WORKSPACE_ROOT
                else "~/.tactus/storage"
            )
            storage_backend = FileStorage(storage_dir=storage_dir)

            # Load procedure metadata
            metadata = storage_backend.load_procedure_metadata(procedure)

            # Filter checkpoints by run_id
            run_checkpoints = [cp for cp in metadata.execution_log if cp.run_id == run_id]

            if not run_checkpoints:
                return jsonify({"error": f"Run not found: {run_id}"}), 404

            # Sort by position
            run_checkpoints.sort(key=lambda c: c.position)

            # Get start/end times
            start_time = run_checkpoints[0].timestamp if run_checkpoints else None
            end_time = run_checkpoints[-1].timestamp if run_checkpoints else None

            # Convert to API format
            run_dict = {
                "run_id": run_id,
                "procedure_name": procedure,
                "file_path": "",
                "start_time": start_time.isoformat() if start_time else None,
                "end_time": end_time.isoformat() if end_time else None,
                "status": "COMPLETED",
                "execution_log": [
                    {
                        "position": cp.position,
                        "type": cp.type,
                        "result": cp.result,
                        "timestamp": cp.timestamp.isoformat() if cp.timestamp else None,
                        "duration_ms": cp.duration_ms,
                        "source_location": (
                            cp.source_location.model_dump() if cp.source_location else None
                        ),
                        "captured_vars": cp.captured_vars,
                    }
                    for cp in run_checkpoints
                ],
                "final_state": metadata.state,
                "breakpoints": [],
            }

            return jsonify(run_dict)
        except Exception as e:
            logger.error("Error getting trace run %s: %s", run_id, e, exc_info=True)
            return jsonify({"error": str(e)}), 500

    @app.route("/api/traces/runs/<run_id>/checkpoints", methods=["GET"])
    def get_run_checkpoints(run_id: str):
        """Get all checkpoints for a specific run."""
        try:
            from pathlib import Path as PathLib
            from tactus.adapters.file_storage import FileStorage

            # Get procedure name from query param
            procedure = request.args.get("procedure")
            if not procedure:
                return jsonify({"error": "procedure parameter required"}), 400

            # Create storage backend
            storage_dir = (
                str(PathLib(WORKSPACE_ROOT) / ".tac" / "storage")
                if WORKSPACE_ROOT
                else "~/.tactus/storage"
            )
            storage_backend = FileStorage(storage_dir=storage_dir)

            # Load procedure metadata
            metadata = storage_backend.load_procedure_metadata(procedure)

            # Filter checkpoints by run_id
            run_checkpoints = [cp for cp in metadata.execution_log if cp.run_id == run_id]

            # Sort by position
            run_checkpoints.sort(key=lambda c: c.position)

            # Convert to dict format
            checkpoints_dict = [
                {
                    "run_id": cp.run_id,
                    "position": cp.position,
                    "name": cp.type,  # Use 'type' field as the name (e.g., "agent_turn")
                    "timestamp": cp.timestamp.isoformat() if cp.timestamp else None,
                    "source_location": (
                        {
                            "file": cp.source_location.file,
                            "line": cp.source_location.line,
                        }
                        if cp.source_location
                        else None
                    ),
                    "data": getattr(cp, "data", None),  # Not all checkpoints have 'data'
                }
                for cp in run_checkpoints
            ]

            return jsonify({"checkpoints": checkpoints_dict})
        except Exception as e:
            logger.error("Error getting checkpoints for run %s: %s", run_id, e, exc_info=True)
            return jsonify({"error": str(e)}), 500

    @app.route("/api/traces/runs/<run_id>/checkpoints/<int:position>", methods=["GET"])
    def get_checkpoint(run_id: str, position: int):
        """Get a specific checkpoint from a run by filtering by run_id."""
        try:
            from pathlib import Path as PathLib
            from tactus.adapters.file_storage import FileStorage

            # Get procedure name from query param
            procedure = request.args.get("procedure")
            if not procedure:
                return jsonify({"error": "procedure parameter required"}), 400

            # Create storage backend
            storage_dir = (
                str(PathLib(WORKSPACE_ROOT) / ".tac" / "storage")
                if WORKSPACE_ROOT
                else "~/.tactus/storage"
            )
            storage_backend = FileStorage(storage_dir=storage_dir)

            # Load procedure metadata
            metadata = storage_backend.load_procedure_metadata(procedure)

            # Find checkpoint by run_id and position
            checkpoint = next(
                (
                    cp
                    for cp in metadata.execution_log
                    if cp.run_id == run_id and cp.position == position
                ),
                None,
            )

            if not checkpoint:
                return (
                    jsonify({"error": f"Checkpoint position {position} not found in run {run_id}"}),
                    404,
                )

            # Convert to API format
            cp_dict = {
                "position": checkpoint.position,
                "type": checkpoint.type,
                "result": checkpoint.result,
                "timestamp": checkpoint.timestamp.isoformat() if checkpoint.timestamp else None,
                "duration_ms": checkpoint.duration_ms,
                "source_location": (
                    checkpoint.source_location.model_dump() if checkpoint.source_location else None
                ),
                "captured_vars": checkpoint.captured_vars,
            }

            return jsonify(cp_dict)
        except Exception as e:
            logger.error(
                "Error getting checkpoint %s@%s: %s",
                run_id,
                position,
                e,
                exc_info=True,
            )
            return jsonify({"error": str(e)}), 500

    @app.route("/api/procedures/<procedure_id>/checkpoints", methods=["DELETE"])
    def clear_checkpoints(procedure_id: str):
        """Clear all checkpoints for a procedure to force fresh execution."""
        try:
            from pathlib import Path as PathLib
            import os

            # Build the checkpoint file path
            storage_dir = (
                PathLib(WORKSPACE_ROOT) / ".tac" / "storage"
                if WORKSPACE_ROOT
                else PathLib.home() / ".tactus" / "storage"
            )
            checkpoint_file = storage_dir / f"{procedure_id}.json"

            if checkpoint_file.exists():
                os.remove(checkpoint_file)
                logger.info("Cleared checkpoints for procedure: %s", procedure_id)
                return jsonify(
                    {"success": True, "message": f"Checkpoints cleared for {procedure_id}"}
                )
            else:
                return jsonify({"success": True, "message": "No checkpoints found"}), 200

        except Exception as e:
            logger.error(
                "Error clearing checkpoints for %s: %s",
                procedure_id,
                e,
                exc_info=True,
            )
            return jsonify({"error": str(e)}), 500

    @app.route("/api/traces/runs/<run_id>/statistics", methods=["GET"])
    def get_run_statistics(run_id: str):
        """Get statistics for a run by filtering checkpoints by run_id."""
        try:
            from pathlib import Path as PathLib
            from tactus.adapters.file_storage import FileStorage
            from collections import Counter

            # Get procedure name from query param
            procedure = request.args.get("procedure")
            if not procedure:
                return jsonify({"error": "procedure parameter required"}), 400

            # Create storage backend
            storage_dir = (
                str(PathLib(WORKSPACE_ROOT) / ".tac" / "storage")
                if WORKSPACE_ROOT
                else "~/.tactus/storage"
            )
            storage_backend = FileStorage(storage_dir=storage_dir)

            # Load procedure metadata
            metadata = storage_backend.load_procedure_metadata(procedure)

            # Filter checkpoints by run_id
            run_checkpoints = [cp for cp in metadata.execution_log if cp.run_id == run_id]

            if not run_checkpoints:
                return jsonify({"error": f"Run not found: {run_id}"}), 404

            # Calculate statistics
            checkpoint_types = Counter(cp.type for cp in run_checkpoints)
            total_duration = sum(cp.duration_ms or 0 for cp in run_checkpoints)
            has_source_locations = sum(1 for cp in run_checkpoints if cp.source_location)

            stats = {
                "run_id": run_id,
                "procedure": procedure,
                "status": "COMPLETED",
                "total_checkpoints": len(run_checkpoints),
                "checkpoints_by_type": dict(checkpoint_types),
                "total_duration_ms": total_duration,
                "has_source_locations": has_source_locations,
            }

            return jsonify(stats)
        except Exception as e:
            logger.error("Error getting statistics for %s: %s", run_id, e, exc_info=True)
            return jsonify({"error": str(e)}), 500

    @app.route("/api/traces/runs/<run_id>/events", methods=["GET"])
    def get_run_events(run_id: str):
        """Get all SSE events for a specific run."""
        try:
            from pathlib import Path as PathLib

            # Determine storage directory
            storage_dir = (
                str(PathLib(WORKSPACE_ROOT) / ".tac" / "storage")
                if WORKSPACE_ROOT
                else "~/.tactus/storage"
            )
            events_dir = PathLib(storage_dir) / "events"
            events_file = events_dir / f"{run_id}.json"

            if not events_file.exists():
                return jsonify({"error": f"Events not found for run {run_id}"}), 404

            # Load events from file
            with open(events_file, "r") as f:
                events = json.load(f)

            return jsonify({"events": events})
        except Exception as e:
            logger.error("Error getting events for %s: %s", run_id, e, exc_info=True)
            return jsonify({"error": str(e)}), 500

    # Coding Assistant - persistent agent instance per session
    coding_assistant = None

    def get_or_create_assistant():
        """Get or create the coding assistant instance."""
        nonlocal coding_assistant
        if coding_assistant is None and WORKSPACE_ROOT:
            try:
                from tactus.ide.coding_assistant import CodingAssistantAgent
                from tactus.core.config_manager import ConfigManager

                # Load configuration
                config_manager = ConfigManager()
                # For IDE, we don't have a procedure file, so use a dummy path
                config = config_manager._load_from_environment()

                # Try to load user config
                for user_path in config_manager._get_user_config_paths():
                    if user_path.exists():
                        user_config = config_manager._load_yaml_file(user_path)
                        if user_config:
                            config = config_manager._deep_merge(config, user_config)
                            break

                coding_assistant = CodingAssistantAgent(WORKSPACE_ROOT, config)
                logger.info("Coding assistant initialized")
            except Exception as e:
                logger.error("Failed to initialize coding assistant: %s", e, exc_info=True)
                raise
        return coding_assistant

    def _clear_caches_impl():
        """Clear cached runtime instances (e.g., after config changes)."""
        nonlocal coding_assistant
        if coding_assistant is not None:
            logger.info("Clearing coding assistant cache")
            coding_assistant = None

    # Set the global cache clearing function
    global _clear_runtime_caches_fn
    _clear_runtime_caches_fn = _clear_caches_impl

    @app.route("/api/chat", methods=["POST"])
    def chat_message():
        """Handle chat messages from the user."""
        try:
            data = request.json
            message = data.get("message")

            if not message:
                return jsonify({"error": "Missing 'message' parameter"}), 400

            if not WORKSPACE_ROOT:
                return jsonify({"error": "No workspace folder selected"}), 400

            # Get or create assistant
            assistant = get_or_create_assistant()

            # Process message
            result = assistant.process_message(message)

            return jsonify(
                {
                    "success": True,
                    "response": result["response"],
                    "tool_calls": result.get("tool_calls", []),
                }
            )

        except Exception as e:
            logger.error("Error handling chat message: %s", e, exc_info=True)
            return jsonify({"error": str(e)}), 500

    @app.route("/api/chat/stream", methods=["POST"])
    def chat_stream():
        """
        Stream chat responses with SSE using our working implementation.

        Request body:
        - workspace_root: Workspace path
        - message: User's message
        - config: Optional config with provider, model, etc.
        """
        try:
            import sys
            import os
            import uuid
            import asyncio

            # Add backend directory to path so we can import our modules
            backend_dir = os.path.join(
                os.path.dirname(__file__), "..", "..", "tactus-ide", "backend"
            )
            if backend_dir not in sys.path:
                sys.path.insert(0, backend_dir)

            from assistant_service import AssistantService

            data = request.json or {}
            workspace_root = data.get("workspace_root") or WORKSPACE_ROOT
            user_message = data.get("message")
            config = data.get(
                "config",
                {"provider": "openai", "model": "gpt-4o", "temperature": 0.7, "max_tokens": 4000},
            )

            if not workspace_root or not user_message:
                return jsonify({"error": "workspace_root and message required"}), 400

            # Create service instance
            conversation_id = str(uuid.uuid4())
            service = AssistantService(workspace_root, config)

            def generate():
                """Generator function that yields SSE events."""
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                try:
                    # Start conversation (configures DSPy LM internally)
                    loop.run_until_complete(service.start_conversation(conversation_id))

                    # Send immediate thinking indicator
                    yield f"data: {json.dumps({'type': 'thinking', 'content': 'Processing your request...'})}\n\n"

                    # Create async generator
                    async_gen = service.send_message(user_message)

                    # Consume events one at a time and yield immediately
                    while True:
                        try:
                            event = loop.run_until_complete(async_gen.__anext__())
                            yield f"data: {json.dumps(event)}\n\n"
                        except StopAsyncIteration:
                            break

                except Exception as e:
                    logger.error("Error streaming message: %s", e, exc_info=True)
                    yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
                finally:
                    loop.close()

            return Response(
                stream_with_context(generate()),
                mimetype="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                    "Connection": "keep-alive",
                },
            )

        except Exception as e:
            logger.error("Error in stream endpoint: %s", e, exc_info=True)
            return jsonify({"error": str(e)}), 500

    @app.route("/api/chat/reset", methods=["POST"])
    def chat_reset():
        """Reset the chat conversation."""
        try:
            assistant = get_or_create_assistant()
            if assistant:
                assistant.reset_conversation()
                return jsonify({"success": True})
            return jsonify({"error": "Assistant not initialized"}), 400
        except Exception as e:
            logger.error("Error resetting chat: %s", e, exc_info=True)
            return jsonify({"error": str(e)}), 500

    @app.route("/api/chat/tools", methods=["GET"])
    def chat_tools():
        """Get available tools for the coding assistant."""
        try:
            assistant = get_or_create_assistant()
            if assistant:
                tools = assistant.get_available_tools()
                return jsonify({"tools": tools})
            return jsonify({"error": "Assistant not initialized"}), 400
        except Exception as e:
            logger.error("Error getting tools: %s", e, exc_info=True)
            return jsonify({"error": str(e)}), 500

    @app.route("/api/lsp", methods=["POST"])
    def lsp_request():
        """Handle LSP requests via HTTP."""
        try:
            message = request.json
            logger.debug("Received LSP message: %s", message.get("method"))
            response = lsp_server.handle_message(message)

            if response:
                return jsonify(response)
            return jsonify({"jsonrpc": "2.0", "id": message.get("id"), "result": None})
        except Exception as e:
            logger.error("Error handling LSP message: %s", e)
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

            logger.debug("Received LSP notification: %s", method)

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
            logger.error("Error handling LSP notification: %s", e)
            return jsonify({"error": str(e)}), 500

    # Register config API routes
    try:
        from tactus.ide.config_server import register_config_routes

        register_config_routes(app)
    except ImportError as e:
        logger.warning("Could not register config routes: %s", e)

    # Serve frontend if dist directory is provided
    # =========================================================================
    # HITL (Human-in-the-Loop) Control Channel Endpoints
    # =========================================================================

    # Global SSE channel instance (shared across requests)
    _sse_channel = None
    # Pending HITL requests (for container control handler)
    _pending_hitl_requests: dict[str, dict] = {}

    def get_sse_channel():
        """Get or create the global SSE channel instance."""
        nonlocal _sse_channel
        if _sse_channel is None:
            from tactus.adapters.channels.sse import SSEControlChannel

            _sse_channel = SSEControlChannel()
        return _sse_channel

    @app.route("/api/hitl/response/<request_id>", methods=["POST"])
    def hitl_response(request_id: str):
        """
        Handle HITL response from IDE.

        Called when user responds to a HITL request in the IDE UI.
        Pushes response to SSEControlChannel which forwards to control loop.

        Request body:
        - value: The response value (boolean, string, dict, etc.)
        """
        try:
            data = request.json or {}
            value = data.get("value")

            logger.info("Received HITL response for %s: %s", request_id, value)

            # Check if this is a container HITL request (pending in our dict)
            if request_id in _pending_hitl_requests:
                pending = _pending_hitl_requests[request_id]
                pending["response"]["value"] = value
                pending["response"]["timed_out"] = False
                pending["response"]["channel_id"] = "sse"
                pending_event = pending.get("event")
                if pending_event is None:
                    raise ValueError(f"Pending HITL request '{request_id}' missing event handle")
                pending_event.set()  # Signal the waiting thread
                logger.info("[HITL] Signaled container handler for %s", request_id)
            else:
                # Push to SSE channel's response queue (for non-container HITL)
                channel = get_sse_channel()
                channel.handle_ide_response(request_id, value)

            return jsonify({"status": "ok", "request_id": request_id})

        except Exception as exc:
            logger.exception("Error handling HITL response for %s", request_id)
            return jsonify({"status": "error", "message": str(exc)}), 400

    @app.route("/api/hitl/stream", methods=["GET"])
    def hitl_stream():
        """
        SSE stream for HITL requests.

        Clients connect to this endpoint to receive hitl.request events
        in real-time. Events include:
        - hitl.request: New HITL request with full context
        - hitl.cancel: Request cancelled (another channel responded)
        """
        logger.info("[HITL-SSE] Client connected to /api/hitl/stream")

        def generate():
            """Generator that yields SSE events from the channel."""
            import asyncio
            import json

            channel = get_sse_channel()

            # Create event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                # Send initial connection event
                connection_event = {
                    "type": "connection",
                    "status": "connected",
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                }
                logger.info("[HITL-SSE] Sending connection event to client")
                yield f"data: {json.dumps(connection_event)}\n\n"

                # Stream events from channel
                while True:
                    # Get next event from channel (non-blocking with timeout)
                    event = loop.run_until_complete(channel.get_next_event())

                    if event:
                        logger.info(
                            "[HITL-SSE] Sending event to client: %s",
                            event.get("type", "unknown"),
                        )
                        yield f"data: {json.dumps(event)}\n\n"
                    else:
                        # Send keepalive comment every second if no events
                        yield ": keepalive\n\n"
                        import time

                        time.sleep(1)

            except GeneratorExit:
                logger.info("HITL SSE client disconnected")
            except Exception as e:
                logger.error("Error in HITL SSE stream: %s", e, exc_info=True)
            finally:
                loop.close()

        return Response(
            stream_with_context(generate()),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

    # =========================================================================
    # Frontend Serving (if enabled)
    # =========================================================================

    if frontend_dist_dir:

        @app.route("/")
        def serve_frontend():
            """Serve the frontend index.html."""
            return app.send_static_file("index.html")

        @app.route("/<path:path>")
        def serve_static_or_frontend(path):
            """Serve static files or index.html for client-side routing."""
            # If the file exists, serve it
            file_path = Path(frontend_dist_dir) / path
            if file_path.exists() and file_path.is_file():
                return app.send_static_file(path)
            # Otherwise, serve index.html for client-side routing (unless it's an API call)
            if not path.startswith("api/"):
                return app.send_static_file("index.html")
            # For API calls that don't match any route, return 404
            return jsonify({"error": "Not found"}), 404

    return app


def main() -> None:
    """
    Run the IDE backend server.

    This enables `python -m tactus.ide.server` which is useful for local development
    and file-watcher based auto-reload workflows.

    Environment variables:
    - TACTUS_IDE_HOST: Host to bind to (default: 127.0.0.1)
    - TACTUS_IDE_PORT: Port to bind to (default: 5001)
    - TACTUS_IDE_WORKSPACE: Initial workspace directory (default: current directory)
    - TACTUS_IDE_LOG_LEVEL: Logging level (default: INFO)
    """
    logging.basicConfig(level=os.environ.get("TACTUS_IDE_LOG_LEVEL", "INFO"))

    host = os.environ.get("TACTUS_IDE_HOST", "127.0.0.1")
    port_str = os.environ.get("TACTUS_IDE_PORT", "5001")
    try:
        port = int(port_str)
    except ValueError:
        raise SystemExit(f"Invalid TACTUS_IDE_PORT: {port_str!r}")

    # Get initial workspace from environment or use current directory
    initial_workspace = os.environ.get("TACTUS_IDE_WORKSPACE")
    if initial_workspace:
        logger.info("Setting initial workspace to: %s", initial_workspace)

    app = create_app(initial_workspace=initial_workspace)
    # NOTE: We intentionally disable Flask's reloader here; external watchers (e.g. watchdog)
    # should restart this process to avoid double-fork behavior.
    app.run(host=host, port=port, debug=False, threaded=True, use_reloader=False)


if __name__ == "__main__":
    main()
