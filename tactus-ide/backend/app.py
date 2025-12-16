"""
Tactus IDE Backend Server

Provides LSP (Language Server Protocol) support and SSE for the Tactus IDE.
This backend runs locally (development) or as a service (production).
"""

import os
import logging
import subprocess
import time
from pathlib import Path
from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from lsp_server import LSPServer
from events import ExecutionEvent

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
                from tactus.core import TactusRuntime
                from tactus.adapters.ide_log import IDELogHandler
                from tactus.adapters.memory import MemoryStorage
                import asyncio
                import threading

                # Send start event
                start_event = ExecutionEvent(
                    lifecycle_stage="start", procedure_id=procedure_id, details={"path": file_path}
                )
                yield f"data: {start_event.model_dump_json()}\n\n"

                # Create log handler to capture structured events
                log_handler = IDELogHandler()

                # Create runtime with log handler
                runtime = TactusRuntime(
                    procedure_id=procedure_id,
                    storage_backend=MemoryStorage(),
                    log_handler=log_handler,
                )

                # Read procedure content
                source_content = path.read_text()

                # Run execution in a separate thread so we can stream events
                result_container = {}

                def run_procedure():
                    try:
                        result = asyncio.run(
                            runtime.execute(source_content, context={}, format="lua")
                        )
                        result_container["result"] = result
                    except Exception as e:
                        result_container["error"] = e

                execution_thread = threading.Thread(target=run_procedure)
                execution_thread.start()

                # Stream events as they come in while execution is running
                while execution_thread.is_alive() or not log_handler.events.empty():
                    events = log_handler.get_events(timeout=0.1)
                    for event in events:
                        try:
                            yield f"data: {event.model_dump_json()}\n\n"
                        except Exception as e:
                            logger.error(f"Failed to serialize event: {e}", exc_info=True)
                            # Send error event instead
                            from events import LogEvent

                            error_event = LogEvent(
                                level="ERROR",
                                message=f"Failed to serialize event: {str(e)}",
                                procedure_id=procedure_id,
                            )
                            yield f"data: {error_event.model_dump_json()}\n\n"
                    time.sleep(0.05)  # Small delay to avoid busy waiting

                # Wait for thread to complete
                execution_thread.join(timeout=1)

                # Get any remaining events
                events = log_handler.get_events(timeout=0.1)
                for event in events:
                    try:
                        yield f"data: {event.model_dump_json()}\n\n"
                    except Exception as e:
                        logger.error(f"Failed to serialize event: {e}", exc_info=True)

                # Check for errors
                if "error" in result_container:
                    raise result_container["error"]

                result = result_container.get("result", {})

                # Send completion event
                complete_event = ExecutionEvent(
                    lifecycle_stage="complete" if result.get("success") else "error",
                    procedure_id=procedure_id,
                    exit_code=0 if result.get("success") else 1,
                    details={"success": result.get("success", False)},
                )
                yield f"data: {complete_event.model_dump_json()}\n\n"

            except Exception as e:
                logger.error(f"Error in streaming execution: {e}", exc_info=True)
                import traceback

                error_event = ExecutionEvent(
                    lifecycle_stage="error",
                    procedure_id=procedure_id,
                    exit_code=1,
                    details={
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "traceback": traceback.format_exc(),
                    },
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
    mock = request.args.get("mock", "false").lower() == "true"
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
                from tactus.testing.events import (
                    TestStartedEvent,
                    TestCompletedEvent,
                    TestScenarioCompletedEvent,
                )
                from events import ExecutionEvent

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
                            total_cost=scenario.total_cost,
                            total_tokens=scenario.total_tokens,
                        )
                        event_json = scenario_event.model_dump_json()
                        yield f"data: {event_json}\n\n"

                # Emit completed event
                complete_event = TestCompletedEvent(result=test_result)
                event_json = complete_event.model_dump_json()
                yield f"data: {event_json}\n\n"

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
                "parameters": { name: ParameterDeclaration },
                "outputs": { name: OutputFieldDeclaration },
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
        from tactus.validation.validator import TactusValidator, ValidationMode

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
                            {"message": e.message, "line": e.location[0] if e.location else None}
                            for e in result.errors
                        ],
                    }
                ),
                400,
            )

        registry = result.registry

        # Extract tools from agents and toolsets
        all_tools = set()
        for agent in registry.agents.values():
            all_tools.update(agent.tools)
        for toolset in registry.toolsets.values():
            if isinstance(toolset, dict) and "tools" in toolset:
                all_tools.update(toolset["tools"])

        # Build metadata response
        metadata = {
            "description": registry.description,
            "parameters": {
                name: {
                    "name": param.name,
                    "type": param.parameter_type,
                    "required": param.required,
                    "default": param.default,
                    "description": getattr(param, "description", None),
                }
                for name, param in registry.parameters.items()
            },
            "outputs": {
                name: {
                    "name": output.name,
                    "type": output.field_type,
                    "required": output.required,
                    "description": getattr(output, "description", None),
                }
                for name, output in registry.outputs.items()
            },
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
        }

        return jsonify({"success": True, "metadata": metadata})

    except Exception as e:
        logger.error(f"Error extracting procedure metadata: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/pydantic-eval/stream", methods=["GET", "POST"])
def pydantic_eval_stream():
    """
    Run Pydantic Evals with SSE streaming output.

    Query params:
    - path: procedure file path (required)
    - runs: number of runs per case (optional, default 1)
    """
    logger.info(f"Pydantic eval stream request: method={request.method}, args={request.args}")

    if request.method == "POST":
        data = request.json or {}
        file_path = data.get("path")
        content = data.get("content")
    else:
        file_path = request.args.get("path")
        content = None

    if not file_path:
        logger.error("Missing 'path' parameter")
        return jsonify({"error": "Missing 'path' parameter"}), 400

    # Get options
    runs = int(request.args.get("runs", "1"))

    try:
        # Resolve path within workspace
        logger.info(f"Resolving path: {file_path}")
        path = _resolve_workspace_path(file_path)
        logger.info(f"Resolved to: {path}")

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
                from tactus.testing.pydantic_eval_runner import TactusPydanticEvalRunner
                from tactus.testing.eval_models import (
                    EvaluationConfig,
                    EvalCase,
                    EvaluatorConfig,
                )
                from events import ExecutionEvent

                # Validate and extract evaluations
                validator = TactusValidator()
                validation_result = validator.validate_file(str(path))

                if not validation_result.valid:
                    error_event = ExecutionEvent(
                        lifecycle_stage="error",
                        procedure_id=procedure_id,
                        details={
                            "error": "Validation failed",
                            "errors": [e.message for e in validation_result.errors],
                        },
                    )
                    yield f"data: {error_event.model_dump_json()}\n\n"
                    return

                if (
                    not validation_result.registry
                    or not validation_result.registry.pydantic_evaluations
                ):
                    error_event = ExecutionEvent(
                        lifecycle_stage="error",
                        procedure_id=procedure_id,
                        details={"error": "No evaluations found in procedure"},
                    )
                    yield f"data: {error_event.model_dump_json()}\n\n"
                    return

                # Emit start event
                start_event = ExecutionEvent(
                    lifecycle_stage="started",
                    procedure_id=procedure_id,
                    details={"type": "pydantic_eval", "runs": runs},
                )
                yield f"data: {start_event.model_dump_json()}\n\n"

                # Parse evaluation config
                eval_dict = validation_result.registry.pydantic_evaluations
                dataset_cases = [EvalCase(**c) for c in eval_dict.get("dataset", [])]
                evaluators = [EvaluatorConfig(**e) for e in eval_dict.get("evaluators", [])]

                eval_config = EvaluationConfig(
                    dataset=dataset_cases,
                    evaluators=evaluators,
                    runs=runs,
                    parallel=False,  # Sequential for IDE streaming
                )

                # Run evaluation
                runner = TactusPydanticEvalRunner(
                    procedure_file=path,
                    eval_config=eval_config,
                    openai_api_key=os.environ.get("OPENAI_API_KEY"),
                )

                report = runner.run_evaluation()

                # Emit results - convert report to dict
                result_details = {
                    "type": "pydantic_eval",
                    "total_cases": len(report.cases) if hasattr(report, "cases") else 0,
                }

                # Add case results
                if hasattr(report, "cases"):
                    result_details["cases"] = []
                    for case in report.cases:
                        case_dict = {
                            "name": case.name,
                            "inputs": case.inputs,
                            "output": case.output,
                            "assertions": case.assertions,
                            "scores": case.scores,
                            "labels": case.labels,
                            "duration": case.task_duration,
                        }
                        result_details["cases"].append(case_dict)

                result_event = ExecutionEvent(
                    lifecycle_stage="completed",
                    procedure_id=procedure_id,
                    details=result_details,
                )
                yield f"data: {result_event.model_dump_json()}\n\n"

            except ImportError as e:
                error_event = ExecutionEvent(
                    lifecycle_stage="error",
                    procedure_id=procedure_id,
                    details={"error": f"pydantic_evals not installed: {e}"},
                )
                yield f"data: {error_event.model_dump_json()}\n\n"
            except Exception as e:
                logger.error(f"Error running Pydantic Evals: {e}", exc_info=True)
                error_event = ExecutionEvent(
                    lifecycle_stage="error",
                    procedure_id=procedure_id,
                    details={"error": str(e)},
                )
                yield f"data: {error_event.model_dump_json()}\n\n"

        return Response(
            stream_with_context(generate_events()),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    except Exception as e:
        logger.error(f"Error setting up Pydantic Evals: {e}", exc_info=True)
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
