"""
Trace Manager - API for managing execution traces and debugging sessions.

Provides operations for querying, filtering, and analyzing procedure execution traces.
"""

import logging
from typing import Optional, List, Dict, Any
from pathlib import Path

from tactus.protocols.storage import StorageBackend
from tactus.protocols.models import ExecutionRun, CheckpointEntry, Breakpoint

logger = logging.getLogger(__name__)


class TraceManager:
    """
    Manages execution traces and debugging sessions.

    Provides API for:
    - Listing and querying execution runs
    - Accessing checkpoint data
    - Managing breakpoints
    - Comparing runs
    - Exporting traces
    """

    def __init__(self, storage: StorageBackend):
        """
        Initialize trace manager.

        Args:
            storage: Storage backend for trace persistence
        """
        self.storage = storage
        logger.info("TraceManager initialized")

    # Run Management

    def list_runs(
        self, procedure_name: Optional[str] = None, limit: Optional[int] = None
    ) -> List[ExecutionRun]:
        """
        List all execution runs, optionally filtered by procedure name.

        Args:
            procedure_name: Optional procedure name filter
            limit: Optional limit on number of runs returned

        Returns:
            List of execution runs, sorted by start time (newest first)
        """
        logger.debug(f"Listing runs (procedure={procedure_name}, limit={limit})")

        runs = self.storage.list_runs(procedure_name=procedure_name)

        if limit:
            runs = runs[:limit]

        return runs

    def get_run(self, run_id: str) -> ExecutionRun:
        """
        Get complete run data.

        Args:
            run_id: Run identifier

        Returns:
            Complete execution run with all checkpoints

        Raises:
            FileNotFoundError: If run not found
        """
        logger.debug(f"Getting run {run_id}")
        return self.storage.load_run(run_id)

    def get_checkpoint(self, run_id: str, position: int) -> CheckpointEntry:
        """
        Get specific checkpoint from a run.

        Args:
            run_id: Run identifier
            position: Checkpoint position (0-indexed)

        Returns:
            Checkpoint entry

        Raises:
            FileNotFoundError: If run not found
            IndexError: If position out of range
        """
        logger.debug(f"Getting checkpoint {position} from run {run_id}")

        run = self.get_run(run_id)

        if position < 0 or position >= len(run.execution_log):
            raise IndexError(
                f"Checkpoint position {position} out of range (0-{len(run.execution_log) - 1})"
            )

        return run.execution_log[position]

    def get_checkpoints(
        self, run_id: str, start: int = 0, end: Optional[int] = None
    ) -> List[CheckpointEntry]:
        """
        Get range of checkpoints from a run.

        Args:
            run_id: Run identifier
            start: Start position (inclusive, 0-indexed)
            end: End position (exclusive, None = end of log)

        Returns:
            List of checkpoint entries
        """
        logger.debug(f"Getting checkpoints {start}:{end} from run {run_id}")

        run = self.get_run(run_id)

        if end is None:
            return run.execution_log[start:]
        else:
            return run.execution_log[start:end]

    # Breakpoint Management

    def set_breakpoint(self, file: str, line: int, condition: Optional[str] = None) -> Breakpoint:
        """
        Set a breakpoint at file:line.

        Args:
            file: File path
            line: Line number (1-indexed)
            condition: Optional Python expression to evaluate

        Returns:
            Created breakpoint
        """
        import uuid

        logger.info(f"Setting breakpoint at {file}:{line}")

        breakpoint = Breakpoint(
            breakpoint_id=str(uuid.uuid4()),
            file=file,
            line=line,
            condition=condition,
            enabled=True,
            hit_count=0,
        )

        # Load existing breakpoints for this file
        # Extract procedure name from file path
        procedure_name = Path(file).stem
        breakpoints = self.storage.load_breakpoints(procedure_name)

        # Add new breakpoint
        breakpoints.append(breakpoint)

        # Save updated list
        self.storage.save_breakpoints(procedure_name, breakpoints)

        return breakpoint

    def remove_breakpoint(self, breakpoint_id: str) -> None:
        """
        Remove a breakpoint.

        Args:
            breakpoint_id: Breakpoint identifier
        """
        logger.info(f"Removing breakpoint {breakpoint_id}")

        # We need to search all breakpoint files
        # For now, this is a simple implementation that loads all
        # TODO: Optimize with an index if this becomes a bottleneck

        # This is a placeholder - in practice we'd need to know which file
        # For now, we'll need to search or maintain an index
        raise NotImplementedError("Remove breakpoint requires file index")

    def list_breakpoints(self, file: Optional[str] = None) -> List[Breakpoint]:
        """
        List all breakpoints, optionally filtered by file.

        Args:
            file: Optional file path filter

        Returns:
            List of breakpoints
        """
        logger.debug(f"Listing breakpoints (file={file})")

        if file:
            procedure_name = Path(file).stem
            return self.storage.load_breakpoints(procedure_name)
        else:
            # List all breakpoints across all procedures
            # This requires iterating through breakpoint directory
            # For now, require a file parameter
            raise NotImplementedError("Listing all breakpoints requires file parameter")

    def toggle_breakpoint(self, breakpoint_id: str, enabled: bool) -> None:
        """
        Enable or disable a breakpoint.

        Args:
            breakpoint_id: Breakpoint identifier
            enabled: Whether to enable or disable
        """
        logger.info(f"Toggling breakpoint {breakpoint_id} to {enabled}")

        # Similar to remove_breakpoint, we need an index or file reference
        raise NotImplementedError("Toggle breakpoint requires file index")

    # Query/Analysis

    def find_checkpoint_after_line(
        self, run_id: str, file: str, line: int
    ) -> Optional[CheckpointEntry]:
        """
        Find nearest checkpoint after specified line.

        This is used for breakpoint mapping: when a user sets a breakpoint at
        a specific line, we find the next checkpoint that will be hit.

        Args:
            run_id: Run identifier
            file: File path
            line: Line number (1-indexed)

        Returns:
            Next checkpoint after the line, or None if no checkpoint found
        """
        logger.debug(f"Finding checkpoint after {file}:{line} in run {run_id}")

        run = self.get_run(run_id)

        # Search for first checkpoint with source location >= line
        for checkpoint in run.execution_log:
            if checkpoint.source_location:
                if (
                    checkpoint.source_location.file == file
                    and checkpoint.source_location.line >= line
                ):
                    return checkpoint

        return None

    def find_checkpoints_by_type(self, run_id: str, checkpoint_type: str) -> List[CheckpointEntry]:
        """
        Find all checkpoints of a specific type.

        Args:
            run_id: Run identifier
            checkpoint_type: Checkpoint type (agent_turn, model_predict, etc.)

        Returns:
            List of matching checkpoints
        """
        logger.debug(f"Finding checkpoints of type '{checkpoint_type}' in run {run_id}")

        run = self.get_run(run_id)

        return [cp for cp in run.execution_log if cp.type == checkpoint_type]

    def compare_runs(self, run_id1: str, run_id2: str) -> Dict[str, Any]:
        """
        Compare two runs for debugging non-determinism.

        Args:
            run_id1: First run identifier
            run_id2: Second run identifier

        Returns:
            Comparison results with differences
        """
        logger.info(f"Comparing runs {run_id1} vs {run_id2}")

        run1 = self.get_run(run_id1)
        run2 = self.get_run(run_id2)

        comparison = {
            "run1": {
                "id": run_id1,
                "procedure": run1.procedure_name,
                "status": run1.status,
                "checkpoint_count": len(run1.execution_log),
            },
            "run2": {
                "id": run_id2,
                "procedure": run2.procedure_name,
                "status": run2.status,
                "checkpoint_count": len(run2.execution_log),
            },
            "differences": [],
        }

        # Compare checkpoint counts
        if len(run1.execution_log) != len(run2.execution_log):
            comparison["differences"].append(
                {
                    "type": "checkpoint_count_mismatch",
                    "run1_count": len(run1.execution_log),
                    "run2_count": len(run2.execution_log),
                }
            )

        # Compare checkpoints position by position
        for i in range(min(len(run1.execution_log), len(run2.execution_log))):
            cp1 = run1.execution_log[i]
            cp2 = run2.execution_log[i]

            # Compare types
            if cp1.type != cp2.type:
                comparison["differences"].append(
                    {
                        "type": "checkpoint_type_mismatch",
                        "position": i,
                        "run1_type": cp1.type,
                        "run2_type": cp2.type,
                    }
                )

            # Compare source locations
            if cp1.source_location and cp2.source_location:
                if cp1.source_location.line != cp2.source_location.line:
                    comparison["differences"].append(
                        {
                            "type": "source_location_mismatch",
                            "position": i,
                            "run1_line": cp1.source_location.line,
                            "run2_line": cp2.source_location.line,
                        }
                    )

            # Compare results (simple equality check)
            if cp1.result != cp2.result:
                comparison["differences"].append(
                    {
                        "type": "result_mismatch",
                        "position": i,
                        "checkpoint_type": cp1.type,
                    }
                )

        return comparison

    def export_trace(self, run_id: str, format: str = "json") -> str:
        """
        Export trace for external analysis.

        Args:
            run_id: Run identifier
            format: Export format (json, csv, etc.)

        Returns:
            Exported trace data as string

        Raises:
            ValueError: If format not supported
        """
        logger.info(f"Exporting run {run_id} as {format}")

        run = self.get_run(run_id)

        if format == "json":
            import json

            return json.dumps(run.model_dump(), indent=2, default=str)
        else:
            raise ValueError(f"Unsupported export format: {format}")

    def get_statistics(self, run_id: str) -> Dict[str, Any]:
        """
        Get statistics about a run.

        Args:
            run_id: Run identifier

        Returns:
            Statistics dictionary with checkpoint counts, timing, etc.
        """
        logger.debug(f"Getting statistics for run {run_id}")

        run = self.get_run(run_id)

        # Count checkpoints by type
        type_counts: Dict[str, int] = {}
        total_duration_ms = 0.0

        for checkpoint in run.execution_log:
            type_counts[checkpoint.type] = type_counts.get(checkpoint.type, 0) + 1
            if checkpoint.duration_ms:
                total_duration_ms += checkpoint.duration_ms

        # Calculate timing stats
        if run.start_time and run.end_time:
            total_time_sec = (run.end_time - run.start_time).total_seconds()
        else:
            total_time_sec = None

        return {
            "run_id": run_id,
            "procedure": run.procedure_name,
            "status": run.status,
            "total_checkpoints": len(run.execution_log),
            "checkpoints_by_type": type_counts,
            "total_duration_ms": total_duration_ms,
            "total_time_sec": total_time_sec,
            "has_source_locations": sum(
                1 for cp in run.execution_log if cp.source_location is not None
            ),
        }
