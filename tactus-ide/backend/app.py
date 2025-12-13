"""
Tactus IDE Backend Server

Provides LSP (Language Server Protocol) support and SSE for the Tactus IDE.
This backend runs locally (development) or as a service (production).
"""

import os
import logging
import subprocess
import threading
import time
from pathlib import Path
from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from lsp_server import LSPServer
from events import ExecutionEvent, OutputEvent

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)
# Let Flask-SocketIO auto-detect the best async mode
socketio = SocketIO(app, cors_allowed_origins="*", logger=False, engineio_logger=False)

# Initialize LSP server
lsp_server = LSPServer()

# Workspace state
WORKSPACE_ROOT = None


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


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok", "service": "tactus-ide-backend"})


@app.route("/api/workspace", methods=["GET", "POST"])
def workspace_operations():
    """
    Handle workspace operations.

    GET: Return current workspace root
    POST: Set workspace root and change working directory
    """
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

            logger.info(f"Workspace set to: {WORKSPACE_ROOT}")

            return jsonify({"success": True, "root": WORKSPACE_ROOT, "name": root_path.name})
        except Exception as e:
            logger.error(f"Error setting workspace {root}: {e}")
            return jsonify({"error": str(e)}), 500


@app.route("/api/tree", methods=["GET"])
def tree_operations():
    """
    List directory contents within the workspace.

    Query params:
    - path: relative path within workspace (default: root)
    """
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
        logger.error(f"Error listing directory {relative_path}: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/file", methods=["GET", "POST"])
def file_operations():
    """
    Handle file operations (read/write files within workspace).

    GET: Read file content (requires workspace-relative path)
    POST: Write file content (requires workspace-relative path)
    """
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

            return jsonify({"success": True, "path": file_path, "absolutePath": str(path)})
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            logger.error(f"Error writing file {file_path}: {e}")
            return jsonify({"error": str(e)}), 500


@app.route("/api/validate", methods=["POST"])
def validate_procedure():
    """
    Validate Tactus procedure code.

    POST body:
    - content: code to validate
    - path: optional workspace-relative path for context
    """
    data = request.json
    content = data.get("content")

    if content is None:
        return jsonify({"error": "Missing 'content' parameter"}), 400

    try:
        # Import validator
        from tactus.validation.validator import TactusValidator

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
                        "severity": err.severity,
                    }
                    for err in result.errors
                ],
            }
        )
    except Exception as e:
        logger.error(f"Error validating code: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/run", methods=["POST"])
def run_procedure():
    """
    Run a Tactus procedure (non-streaming, backward compatibility).

    POST body:
    - path: workspace-relative path to procedure file
    - content: optional content to save before running
    """
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
        logger.error(f"Error running procedure {file_path}: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/run/stream", methods=["GET", "POST"])
def run_procedure_stream():
    """
    Run a Tactus procedure with SSE streaming output.

    For GET: Query param 'path' (required)
    For POST: JSON body with 'path' (required) and optional 'content'
    """
    if request.method == "POST":
        data = request.json or {}
        file_path = data.get("path")
        content = data.get("content")
    else:
        file_path = request.args.get("path")
        content = None  # Don't pass content via URL params (too large)

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

        procedure_id = path.stem

        def generate_events():
            """Generator function that yields SSE events."""
            try:
                # Send start event
                start_event = ExecutionEvent(
                    lifecycle_stage="start", procedure_id=procedure_id, details={"path": file_path}
                )
                yield f"data: {start_event.model_dump_json()}\n\n"

                # Run the procedure using tactus CLI and capture output
                process = subprocess.Popen(
                    ["tactus", "run", str(path)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    cwd=WORKSPACE_ROOT,
                    bufsize=1,  # Line buffered
                    universal_newlines=True,
                )

                # Use threads to read stdout and stderr without blocking
                import queue as q

                output_queue = q.Queue()

                def read_stream(stream, stream_name):
                    try:
                        for line in iter(stream.readline, ""):
                            if line:
                                output_queue.put((stream_name, line.rstrip("\n")))
                    except Exception as e:
                        logger.error(f"Error reading {stream_name}: {e}")
                    finally:
                        stream.close()

                stdout_thread = threading.Thread(
                    target=read_stream, args=(process.stdout, "stdout")
                )
                stderr_thread = threading.Thread(
                    target=read_stream, args=(process.stderr, "stderr")
                )
                stdout_thread.daemon = True
                stderr_thread.daemon = True
                stdout_thread.start()
                stderr_thread.start()

                # Poll for output until process completes
                while process.poll() is None or not output_queue.empty():
                    try:
                        stream_name, content = output_queue.get(timeout=0.1)
                        output_event = OutputEvent(
                            stream=stream_name, content=content, procedure_id=procedure_id
                        )
                        yield f"data: {output_event.model_dump_json()}\n\n"
                    except q.Empty:
                        # No output available, just continue polling
                        time.sleep(0.05)

                # Wait for threads to finish
                stdout_thread.join(timeout=1)
                stderr_thread.join(timeout=1)

                # Send completion event
                exit_code = process.returncode
                complete_event = ExecutionEvent(
                    lifecycle_stage="complete" if exit_code == 0 else "error",
                    procedure_id=procedure_id,
                    exit_code=exit_code,
                    details={"success": exit_code == 0},
                )
                yield f"data: {complete_event.model_dump_json()}\n\n"

            except Exception as e:
                logger.error(f"Error in streaming execution: {e}", exc_info=True)
                error_event = ExecutionEvent(
                    lifecycle_stage="error", procedure_id=procedure_id, details={"error": str(e)}
                )
                yield f"data: {error_event.model_dump_json()}\n\n"

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
        logger.error(f"Error setting up streaming execution: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/test/stream", methods=["GET", "POST"])
def test_procedure_stream():
    """
    Run BDD tests with SSE streaming output.

    Query params:
    - path: procedure file path (required)
    - mock: use mock mode (optional, default true)
    - scenario: specific scenario name (optional)
    - parallel: run in parallel (optional, default false)
    """
    if request.method == "POST":
        data = request.json or {}
        file_path = data.get("path")
        content = data.get("content")
    else:
        file_path = request.args.get("path")
        content = None

    if not file_path:
        return jsonify({"error": "Missing 'path' parameter"}), 400

    # Get options
    mock = request.args.get("mock", "true").lower() == "true"
    parallel = request.args.get("parallel", "false").lower() == "true"

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

        procedure_id = path.stem

        def generate_events():
            """Generator function that yields SSE test events."""
            try:
                from tactus.validation import TactusValidator
                from tactus.testing import TactusTestRunner, GherkinParser
                from events import (
                    TestStartedEvent,
                    TestCompletedEvent,
                    TestScenarioCompletedEvent,
                    ExecutionEvent,
                )

                # Validate and extract specifications
                validator = TactusValidator()
                validation_result = validator.validate_file(str(path))

                if not validation_result.valid:
                    # Emit validation error
                    error_event = ExecutionEvent(
                        lifecycle_stage="error",
                        procedure_id=procedure_id,
                        details={
                            "error": "Validation failed",
                            "errors": [
                                {"message": e.message, "severity": e.severity}
                                for e in validation_result.errors
                            ],
                        },
                    )
                    yield f"data: {error_event.model_dump_json()}\n\n"
                    return

                if (
                    not validation_result.registry
                    or not validation_result.registry.gherkin_specifications
                ):
                    # No specifications found
                    error_event = ExecutionEvent(
                        lifecycle_stage="error",
                        procedure_id=procedure_id,
                        details={"error": "No specifications found in procedure"},
                    )
                    yield f"data: {error_event.model_dump_json()}\n\n"
                    return

                # Setup test runner
                mock_tools = {"done": {"status": "ok"}} if mock else None
                runner = TactusTestRunner(path, mock_tools=mock_tools)
                runner.setup(validation_result.registry.gherkin_specifications)

                # Get parsed feature to count scenarios
                parser = GherkinParser()
                parsed_feature = parser.parse(validation_result.registry.gherkin_specifications)
                total_scenarios = len(parsed_feature.scenarios)

                # Emit started event
                start_event = TestStartedEvent(
                    procedure_file=str(path), total_scenarios=total_scenarios
                )
                yield f"data: {start_event.model_dump_json()}\n\n"

                # Run tests
                test_result = runner.run_tests(parallel=parallel)

                # Emit scenario completion events
                for feature in test_result.features:
                    for scenario in feature.scenarios:
                        scenario_event = TestScenarioCompletedEvent(
                            scenario_name=scenario.name,
                            status=scenario.status,
                            duration=scenario.duration,
                        )
                        yield f"data: {scenario_event.model_dump_json()}\n\n"

                # Emit completed event
                complete_event = TestCompletedEvent(result=test_result)
                yield f"data: {complete_event.model_dump_json()}\n\n"

                # Cleanup
                runner.cleanup()

            except Exception as e:
                logger.error(f"Error in test execution: {e}", exc_info=True)
                error_event = ExecutionEvent(
                    lifecycle_stage="error", procedure_id=procedure_id, details={"error": str(e)}
                )
                yield f"data: {error_event.model_dump_json()}\n\n"

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
        logger.error(f"Error setting up test execution: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/evaluate/stream", methods=["GET", "POST"])
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
    if request.method == "POST":
        data = request.json or {}
        file_path = data.get("path")
        content = data.get("content")
    else:
        file_path = request.args.get("path")
        content = None

    if not file_path:
        return jsonify({"error": "Missing 'path' parameter"}), 400

    # Get options
    runs = int(request.args.get("runs", "10"))
    mock = request.args.get("mock", "true").lower() == "true"
    parallel = request.args.get("parallel", "true").lower() == "true"

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

        procedure_id = path.stem

        def generate_events():
            """Generator function that yields SSE evaluation events."""
            try:
                from tactus.validation import TactusValidator
                from tactus.testing import TactusEvaluationRunner, GherkinParser
                from events import (
                    EvaluationStartedEvent,
                    EvaluationCompletedEvent,
                    EvaluationProgressEvent,
                    ExecutionEvent,
                )

                # Validate and extract specifications
                validator = TactusValidator()
                validation_result = validator.validate_file(str(path))

                if not validation_result.valid:
                    error_event = ExecutionEvent(
                        lifecycle_stage="error",
                        procedure_id=procedure_id,
                        details={
                            "error": "Validation failed",
                            "errors": [
                                {"message": e.message, "severity": e.severity}
                                for e in validation_result.errors
                            ],
                        },
                    )
                    yield f"data: {error_event.model_dump_json()}\n\n"
                    return

                if (
                    not validation_result.registry
                    or not validation_result.registry.gherkin_specifications
                ):
                    error_event = ExecutionEvent(
                        lifecycle_stage="error",
                        procedure_id=procedure_id,
                        details={"error": "No specifications found in procedure"},
                    )
                    yield f"data: {error_event.model_dump_json()}\n\n"
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
                start_event = EvaluationStartedEvent(
                    procedure_file=str(path),
                    total_scenarios=total_scenarios,
                    runs_per_scenario=runs,
                )
                yield f"data: {start_event.model_dump_json()}\n\n"

                # Run evaluation
                eval_results = evaluator.evaluate_all(runs=runs, parallel=parallel)

                # Emit progress/completion events for each scenario
                for eval_result in eval_results:
                    progress_event = EvaluationProgressEvent(
                        scenario_name=eval_result.scenario_name,
                        completed_runs=eval_result.total_runs,
                        total_runs=eval_result.total_runs,
                    )
                    yield f"data: {progress_event.model_dump_json()}\n\n"

                # Emit completed event
                complete_event = EvaluationCompletedEvent(results=eval_results)
                yield f"data: {complete_event.model_dump_json()}\n\n"

                # Cleanup
                evaluator.cleanup()

            except Exception as e:
                logger.error(f"Error in evaluation execution: {e}", exc_info=True)
                error_event = ExecutionEvent(
                    lifecycle_stage="error", procedure_id=procedure_id, details={"error": str(e)}
                )
                yield f"data: {error_event.model_dump_json()}\n\n"

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
        logger.error(f"Error setting up evaluation execution: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@socketio.on("connect")
def handle_connect():
    """Handle WebSocket connection."""
    logger.info("Client connected")
    emit("connected", {"status": "ok"})


@socketio.on("disconnect")
def handle_disconnect():
    """Handle WebSocket disconnection."""
    logger.info("Client disconnected")


@socketio.on("lsp")
def handle_lsp_message(message):
    """
    Handle LSP JSON-RPC messages via WebSocket.

    LSP protocol uses JSON-RPC 2.0 format:
    {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "textDocument/didChange",
        "params": {...}
    }
    """
    try:
        logger.debug(f"Received LSP message: {message.get('method')}")
        response = lsp_server.handle_message(message)

        if response:
            emit("lsp", response)
    except Exception as e:
        logger.error(f"Error handling LSP message: {e}")
        error_response = {
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "error": {"code": -32603, "message": str(e)},
        }
        emit("lsp", error_response)


@socketio.on("lsp_notification")
def handle_lsp_notification(message):
    """Handle LSP notifications (no response expected)."""
    try:
        logger.debug(f"Received LSP notification: {message.get('method')}")
        lsp_server.handle_notification(message)
    except Exception as e:
        logger.error(f"Error handling LSP notification: {e}")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))  # Changed from 5000 to 5001 (macOS AirPlay uses 5000)
    logger.info(f"Starting Tactus IDE Backend on port {port}")
    # Use socketio.run which handles WebSocket properly
    socketio.run(
        app,
        host="127.0.0.1",
        port=port,
        debug=False,
        use_reloader=False,
        log_output=False,
        allow_unsafe_werkzeug=True,
    )
