"""
Communication protocol between host and container processes.

Defines the data structures for serializing execution requests and results
over stdio between the host process and the sandboxed container.
"""

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel


def _json_serializer(obj: Any) -> Any:
    """Custom JSON serializer for objects not natively serializable."""
    if isinstance(obj, BaseModel):
        return obj.model_dump(mode="json")
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


class ExecutionStatus(str, Enum):
    """Status of sandbox execution."""

    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class ExecutionRequest:
    """
    Request sent from host to container for procedure execution.

    Serialized as JSON over stdin to the container process.
    """

    # Procedure source code (.tac file content)
    source: str

    # Working directory path (inside container)
    working_dir: str = "/workspace"

    # Input parameters for the procedure
    params: dict[str, Any] = field(default_factory=dict)

    # Unique execution ID for tracking
    execution_id: Optional[str] = None

    # Run ID for checkpoint isolation across multiple executions
    run_id: Optional[str] = None

    # Source file path (for error messages)
    source_file_path: Optional[str] = None

    # Source format: "lua" for .tac files, "yaml" for legacy YAML format
    format: str = "lua"

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(asdict(self), indent=None, separators=(",", ":"))

    @classmethod
    def from_json(cls, json_str: str) -> "ExecutionRequest":
        """Deserialize from JSON string."""
        data = json.loads(json_str)
        return cls(**data)


@dataclass
class ExecutionResult:
    """
    Result returned from container to host after execution.

    Serialized as JSON over stdout from the container process.
    """

    # Execution status
    status: ExecutionStatus

    # Result value (if successful)
    result: Optional[Any] = None

    # Error message (if failed)
    error: Optional[str] = None

    # Error type/class name
    error_type: Optional[str] = None

    # Stack trace (if failed)
    traceback: Optional[str] = None

    # Execution duration in seconds
    duration_seconds: float = 0.0

    # Exit code suggestion
    exit_code: int = 0

    # Structured logs from execution
    logs: list[dict[str, Any]] = field(default_factory=list)

    # Metadata about the execution
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        """Serialize to JSON string."""
        data = asdict(self)
        # Convert enum to string for JSON
        data["status"] = self.status.value
        return json.dumps(data, indent=None, separators=(",", ":"), default=_json_serializer)

    @classmethod
    def from_json(cls, json_str: str) -> "ExecutionResult":
        """Deserialize from JSON string."""
        data = json.loads(json_str)
        # Convert string back to enum
        data["status"] = ExecutionStatus(data["status"])
        return cls(**data)

    @classmethod
    def success(
        cls,
        result: Any,
        duration_seconds: float = 0.0,
        logs: Optional[list[dict[str, Any]]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> "ExecutionResult":
        """Create a successful result."""
        return cls(
            status=ExecutionStatus.SUCCESS,
            result=result,
            duration_seconds=duration_seconds,
            exit_code=0,
            logs=logs or [],
            metadata=metadata or {},
        )

    @classmethod
    def failure(
        cls,
        error: str,
        error_type: Optional[str] = None,
        traceback: Optional[str] = None,
        duration_seconds: float = 0.0,
        exit_code: int = 1,
        logs: Optional[list[dict[str, Any]]] = None,
    ) -> "ExecutionResult":
        """Create a failed result."""
        return cls(
            status=ExecutionStatus.ERROR,
            error=error,
            error_type=error_type,
            traceback=traceback,
            duration_seconds=duration_seconds,
            exit_code=exit_code,
            logs=logs or [],
        )

    @classmethod
    def timeout(
        cls,
        duration_seconds: float,
        logs: Optional[list[dict[str, Any]]] = None,
    ) -> "ExecutionResult":
        """Create a timeout result."""
        return cls(
            status=ExecutionStatus.TIMEOUT,
            error="Execution timed out",
            duration_seconds=duration_seconds,
            exit_code=124,  # Standard timeout exit code
            logs=logs or [],
        )


# Protocol markers for parsing stdout
# The result JSON is wrapped in markers to distinguish it from other output
RESULT_START_MARKER = "<<<TACTUS_RESULT_START>>>"
RESULT_END_MARKER = "<<<TACTUS_RESULT_END>>>"


def wrap_result_for_stdout(result: ExecutionResult) -> str:
    """
    Wrap a result in markers for stdout transmission.

    This allows the host to distinguish the structured result
    from any other output (logs, debug prints, etc.)
    """
    return f"{RESULT_START_MARKER}\n{result.to_json()}\n{RESULT_END_MARKER}\n"


def extract_result_from_stdout(stdout: str) -> Optional[ExecutionResult]:
    """
    Extract the result from stdout, looking for markers.

    Returns None if no valid result is found.
    """
    start_marker_index = stdout.find(RESULT_START_MARKER)
    if start_marker_index == -1:
        return None

    end_marker_index = stdout.find(RESULT_END_MARKER, start_marker_index)
    if end_marker_index == -1:
        return None

    # Extract JSON between markers
    json_start = start_marker_index + len(RESULT_START_MARKER)
    json_str = stdout[json_start:end_marker_index].strip()

    try:
        return ExecutionResult.from_json(json_str)
    except (json.JSONDecodeError, TypeError, KeyError):
        return None
