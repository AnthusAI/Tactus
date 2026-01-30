"""
Tests for execution tracing and debugging features.
"""

import tempfile
from datetime import datetime, timezone, timedelta

import pytest

from tactus.protocols.models import (
    SourceLocation,
    CheckpointEntry,
    Breakpoint,
    ExecutionRun,
)
from tactus.adapters.file_storage import FileStorage
from tactus.tracing import TraceManager
from tactus.core.execution_context import BaseExecutionContext


class TestSourceLocation:
    """Test SourceLocation model."""

    def test_create_source_location(self):
        """Test creating a source location."""
        loc = SourceLocation(
            file="/path/to/file.tac",
            line=42,
            function="test_function",
            code_context="local x = 10\nprint(x)\nreturn x",
        )

        assert loc.file == "/path/to/file.tac"
        assert loc.line == 42
        assert loc.function == "test_function"
        assert "local x = 10" in loc.code_context

    def test_source_location_without_optional_fields(self):
        """Test source location with only required fields."""
        loc = SourceLocation(file="/path/to/file.tac", line=42)

        assert loc.file == "/path/to/file.tac"
        assert loc.line == 42
        assert loc.function is None
        assert loc.code_context is None


class TestCheckpointEntry:
    """Test CheckpointEntry model with source locations."""

    def test_checkpoint_with_source_location(self):
        """Test checkpoint entry with source location."""
        loc = SourceLocation(file="/test.tac", line=10, function="main")

        checkpoint = CheckpointEntry(
            position=0,
            type="agent_turn",
            result={"text": "Hello"},
            timestamp=datetime.now(timezone.utc),
            duration_ms=150.5,
            source_location=loc,
            captured_vars={"state": {"count": 1}},
        )

        assert checkpoint.position == 0
        assert checkpoint.type == "agent_turn"
        assert checkpoint.source_location.file == "/test.tac"
        assert checkpoint.source_location.line == 10
        assert checkpoint.captured_vars["state"]["count"] == 1

    def test_checkpoint_without_source_location(self):
        """Test checkpoint without source location (backward compatibility)."""
        checkpoint = CheckpointEntry(
            position=0,
            type="agent_turn",
            result={"text": "Hello"},
            timestamp=datetime.now(timezone.utc),
        )

        assert checkpoint.source_location is None
        assert checkpoint.captured_vars is None


class TestBreakpoint:
    """Test Breakpoint model."""

    def test_create_breakpoint(self):
        """Test creating a breakpoint."""
        bp = Breakpoint(
            breakpoint_id="bp-123",
            file="/test.tac",
            line=42,
            condition="state.count > 5",
            enabled=True,
            hit_count=0,
        )

        assert bp.breakpoint_id == "bp-123"
        assert bp.file == "/test.tac"
        assert bp.line == 42
        assert bp.condition == "state.count > 5"
        assert bp.enabled is True
        assert bp.hit_count == 0

    def test_breakpoint_defaults(self):
        """Test breakpoint with default values."""
        bp = Breakpoint(breakpoint_id="bp-456", file="/test.tac", line=10)

        assert bp.condition is None
        assert bp.enabled is True
        assert bp.hit_count == 0


class TestExecutionRun:
    """Test ExecutionRun model."""

    def test_create_execution_run(self):
        """Test creating an execution run."""
        loc = SourceLocation(file="/test.tac", line=10)
        checkpoint = CheckpointEntry(
            position=0,
            type="agent_turn",
            result={"text": "Hello"},
            timestamp=datetime.now(timezone.utc),
            source_location=loc,
        )

        run = ExecutionRun(
            run_id="run-123",
            procedure_name="test_proc",
            file_path="/test.tac",
            start_time=datetime.now(timezone.utc),
            status="RUNNING",
            execution_log=[checkpoint],
            final_state={"count": 1},
        )

        assert run.run_id == "run-123"
        assert run.procedure_name == "test_proc"
        assert run.status == "RUNNING"
        assert len(run.execution_log) == 1
        assert run.execution_log[0].source_location.line == 10


class TestFileStorageTracing:
    """Test FileStorage tracing methods."""

    def test_save_and_load_run(self):
        """Test saving and loading a run."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = FileStorage(tmpdir)

            # Create run with checkpoints
            loc = SourceLocation(file="/test.tac", line=42, function="main")
            checkpoint = CheckpointEntry(
                position=0,
                type="agent_turn",
                result={"text": "Hello"},
                timestamp=datetime.now(timezone.utc),
                duration_ms=100.0,
                source_location=loc,
                captured_vars={"count": 1},
            )

            run = ExecutionRun(
                run_id="test-run-1",
                procedure_name="test_proc",
                file_path="/test.tac",
                start_time=datetime.now(timezone.utc),
                status="COMPLETED",
                execution_log=[checkpoint],
                final_state={"count": 1},
            )

            # Save run
            storage.save_run(run)

            # Load run
            loaded_run = storage.load_run("test-run-1")

            assert loaded_run.run_id == "test-run-1"
            assert loaded_run.procedure_name == "test_proc"
            assert loaded_run.status == "COMPLETED"
            assert len(loaded_run.execution_log) == 1
            assert loaded_run.execution_log[0].source_location.file == "/test.tac"
            assert loaded_run.execution_log[0].source_location.line == 42
            assert loaded_run.execution_log[0].captured_vars["count"] == 1

    def test_list_runs(self):
        """Test listing runs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = FileStorage(tmpdir)

            # Create multiple runs
            for i in range(3):
                run = ExecutionRun(
                    run_id=f"run-{i}",
                    procedure_name=f"proc-{i}",
                    file_path=f"/test-{i}.tac",
                    start_time=datetime.now(timezone.utc),
                    status="COMPLETED",
                )
                storage.save_run(run)

            # List all runs
            runs = storage.list_runs()
            assert len(runs) == 3

            # List runs for specific procedure
            runs = storage.list_runs(procedure_name="proc-1")
            assert len(runs) == 1
            assert runs[0].procedure_name == "proc-1"

    def test_save_and_load_breakpoints(self):
        """Test saving and loading breakpoints."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = FileStorage(tmpdir)

            # Create breakpoints
            breakpoints = [
                Breakpoint(breakpoint_id="bp-1", file="/test.tac", line=10),
                Breakpoint(
                    breakpoint_id="bp-2",
                    file="/test.tac",
                    line=20,
                    condition="state.count > 5",
                ),
            ]

            # Save breakpoints
            storage.save_breakpoints("test_proc", breakpoints)

            # Load breakpoints
            loaded_bps = storage.load_breakpoints("test_proc")

            assert len(loaded_bps) == 2
            assert loaded_bps[0].line == 10
            assert loaded_bps[1].line == 20
            assert loaded_bps[1].condition == "state.count > 5"

    def test_load_nonexistent_breakpoints(self):
        """Test loading breakpoints that don't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = FileStorage(tmpdir)

            # Load non-existent breakpoints
            breakpoints = storage.load_breakpoints("nonexistent_proc")

            assert breakpoints == []


class TestTraceManager:
    """Test TraceManager API."""

    def test_list_runs(self):
        """Test listing runs via TraceManager."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = FileStorage(tmpdir)
            trace_mgr = TraceManager(storage)

            # Create runs
            for i in range(5):
                run = ExecutionRun(
                    run_id=f"run-{i}",
                    procedure_name="test_proc",
                    file_path="/test.tac",
                    start_time=datetime.now(timezone.utc),
                    status="COMPLETED",
                )
                storage.save_run(run)

            # List runs with limit
            runs = trace_mgr.list_runs(limit=3)
            assert len(runs) == 3

            # List all runs
            runs = trace_mgr.list_runs()
            assert len(runs) == 5

    def test_get_run(self):
        """Test getting a specific run."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = FileStorage(tmpdir)
            trace_mgr = TraceManager(storage)

            # Create and save run
            run = ExecutionRun(
                run_id="test-run",
                procedure_name="test_proc",
                file_path="/test.tac",
                start_time=datetime.now(timezone.utc),
                status="COMPLETED",
            )
            storage.save_run(run)

            # Get run
            loaded_run = trace_mgr.get_run("test-run")
            assert loaded_run.run_id == "test-run"

    def test_get_checkpoint(self):
        """Test getting a specific checkpoint."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = FileStorage(tmpdir)
            trace_mgr = TraceManager(storage)

            # Create run with multiple checkpoints
            checkpoints = [
                CheckpointEntry(
                    position=i,
                    type="agent_turn",
                    result={"text": f"Message {i}"},
                    timestamp=datetime.now(timezone.utc),
                    source_location=SourceLocation(file="/test.tac", line=10 + i),
                )
                for i in range(3)
            ]

            run = ExecutionRun(
                run_id="test-run",
                procedure_name="test_proc",
                file_path="/test.tac",
                start_time=datetime.now(timezone.utc),
                status="COMPLETED",
                execution_log=checkpoints,
            )
            storage.save_run(run)

            # Get specific checkpoint
            checkpoint = trace_mgr.get_checkpoint("test-run", 1)
            assert checkpoint.position == 1
            assert checkpoint.source_location.line == 11

    def test_get_checkpoint_range(self):
        """Test getting a range of checkpoints."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = FileStorage(tmpdir)
            trace_mgr = TraceManager(storage)

            # Create run with multiple checkpoints
            checkpoints = [
                CheckpointEntry(
                    position=i,
                    type="agent_turn",
                    result={"text": f"Message {i}"},
                    timestamp=datetime.now(timezone.utc),
                )
                for i in range(10)
            ]

            run = ExecutionRun(
                run_id="test-run",
                procedure_name="test_proc",
                file_path="/test.tac",
                start_time=datetime.now(timezone.utc),
                status="COMPLETED",
                execution_log=checkpoints,
            )
            storage.save_run(run)

            # Get checkpoint range
            checkpoints = trace_mgr.get_checkpoints("test-run", start=2, end=5)
            assert len(checkpoints) == 3
            assert checkpoints[0].position == 2
            assert checkpoints[-1].position == 4

    def test_find_checkpoint_after_line(self):
        """Test finding checkpoint after a specific line."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = FileStorage(tmpdir)
            trace_mgr = TraceManager(storage)

            # Create run with checkpoints at different lines
            checkpoints = [
                CheckpointEntry(
                    position=0,
                    type="agent_turn",
                    result={"text": "Message 1"},
                    timestamp=datetime.now(timezone.utc),
                    source_location=SourceLocation(file="/test.tac", line=10),
                ),
                CheckpointEntry(
                    position=1,
                    type="agent_turn",
                    result={"text": "Message 2"},
                    timestamp=datetime.now(timezone.utc),
                    source_location=SourceLocation(file="/test.tac", line=25),
                ),
                CheckpointEntry(
                    position=2,
                    type="agent_turn",
                    result={"text": "Message 3"},
                    timestamp=datetime.now(timezone.utc),
                    source_location=SourceLocation(file="/test.tac", line=40),
                ),
            ]

            run = ExecutionRun(
                run_id="test-run",
                procedure_name="test_proc",
                file_path="/test.tac",
                start_time=datetime.now(timezone.utc),
                status="COMPLETED",
                execution_log=checkpoints,
            )
            storage.save_run(run)

            # Find checkpoint after line 15 (should be line 25)
            checkpoint = trace_mgr.find_checkpoint_after_line("test-run", "/test.tac", 15)
            assert checkpoint is not None
            assert checkpoint.source_location.line == 25

            # Find checkpoint after line 30 (should be line 40)
            checkpoint = trace_mgr.find_checkpoint_after_line("test-run", "/test.tac", 30)
            assert checkpoint is not None
            assert checkpoint.source_location.line == 40

            # Find checkpoint after line 50 (should be None)
            checkpoint = trace_mgr.find_checkpoint_after_line("test-run", "/test.tac", 50)
            assert checkpoint is None

    def test_find_checkpoint_after_line_skips_missing_source(self):
        """Test find_checkpoint_after_line ignores checkpoints without source."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = FileStorage(tmpdir)
            trace_mgr = TraceManager(storage)

            checkpoints = [
                CheckpointEntry(
                    position=0,
                    type="agent_turn",
                    result={"text": "Message 1"},
                    timestamp=datetime.now(timezone.utc),
                    source_location=None,
                ),
                CheckpointEntry(
                    position=1,
                    type="agent_turn",
                    result={"text": "Message 2"},
                    timestamp=datetime.now(timezone.utc),
                    source_location=SourceLocation(file="/test.tac", line=15),
                ),
            ]

            run = ExecutionRun(
                run_id="test-run",
                procedure_name="test_proc",
                file_path="/test.tac",
                start_time=datetime.now(timezone.utc),
                status="COMPLETED",
                execution_log=checkpoints,
            )
            storage.save_run(run)

            checkpoint = trace_mgr.find_checkpoint_after_line("test-run", "/test.tac", 1)
            assert checkpoint is not None
            assert checkpoint.source_location.line == 15

    def test_compare_runs(self):
        """Test comparing two runs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = FileStorage(tmpdir)
            trace_mgr = TraceManager(storage)

            # Create two similar runs with differences
            run1 = ExecutionRun(
                run_id="run-1",
                procedure_name="test_proc",
                file_path="/test.tac",
                start_time=datetime.now(timezone.utc),
                status="COMPLETED",
                execution_log=[
                    CheckpointEntry(
                        position=0,
                        type="agent_turn",
                        result={"text": "Hello"},
                        timestamp=datetime.now(timezone.utc),
                        source_location=SourceLocation(file="/test.tac", line=10),
                    ),
                    CheckpointEntry(
                        position=1,
                        type="agent_turn",
                        result={"text": "World"},
                        timestamp=datetime.now(timezone.utc),
                        source_location=SourceLocation(file="/test.tac", line=20),
                    ),
                ],
            )

            run2 = ExecutionRun(
                run_id="run-2",
                procedure_name="test_proc",
                file_path="/test.tac",
                start_time=datetime.now(timezone.utc),
                status="COMPLETED",
                execution_log=[
                    CheckpointEntry(
                        position=0,
                        type="agent_turn",
                        result={"text": "Hello"},
                        timestamp=datetime.now(timezone.utc),
                        source_location=SourceLocation(file="/test.tac", line=10),
                    ),
                    CheckpointEntry(
                        position=1,
                        type="model_predict",  # Different type
                        result={"text": "Different"},  # Different result
                        timestamp=datetime.now(timezone.utc),
                        source_location=SourceLocation(file="/test.tac", line=25),  # Different line
                    ),
                ],
            )

            storage.save_run(run1)
            storage.save_run(run2)

            # Compare runs
            comparison = trace_mgr.compare_runs("run-1", "run-2")

            assert comparison["run1"]["checkpoint_count"] == 2
            assert comparison["run2"]["checkpoint_count"] == 2
            assert len(comparison["differences"]) > 0

            # Should detect type mismatch
            type_diffs = [
                d for d in comparison["differences"] if d["type"] == "checkpoint_type_mismatch"
            ]
            assert len(type_diffs) == 1
            assert type_diffs[0]["position"] == 1

            # Should detect source location mismatch
            loc_diffs = [
                d for d in comparison["differences"] if d["type"] == "source_location_mismatch"
            ]
            assert len(loc_diffs) == 1

    def test_compare_runs_with_matching_sources(self):
        """Test comparing runs with matching source locations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = FileStorage(tmpdir)
            trace_mgr = TraceManager(storage)

            checkpoints = [
                CheckpointEntry(
                    position=0,
                    type="agent_turn",
                    result={"text": "Hello"},
                    timestamp=datetime.now(timezone.utc),
                    source_location=SourceLocation(file="/test.tac", line=10),
                )
            ]

            run1 = ExecutionRun(
                run_id="run-1",
                procedure_name="test_proc",
                file_path="/test.tac",
                start_time=datetime.now(timezone.utc),
                status="COMPLETED",
                execution_log=checkpoints,
            )
            run2 = ExecutionRun(
                run_id="run-2",
                procedure_name="test_proc",
                file_path="/test.tac",
                start_time=datetime.now(timezone.utc),
                status="COMPLETED",
                execution_log=checkpoints,
            )

            storage.save_run(run1)
            storage.save_run(run2)

            comparison = trace_mgr.compare_runs("run-1", "run-2")

            assert comparison["differences"] == []

    def test_compare_runs_with_missing_source_location(self):
        """Test comparing runs when source locations are missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = FileStorage(tmpdir)
            trace_mgr = TraceManager(storage)

            run1 = ExecutionRun(
                run_id="run-1",
                procedure_name="test_proc",
                file_path="/test.tac",
                start_time=datetime.now(timezone.utc),
                status="COMPLETED",
                execution_log=[
                    CheckpointEntry(
                        position=0,
                        type="agent_turn",
                        result={"text": "Hello"},
                        timestamp=datetime.now(timezone.utc),
                        source_location=None,
                    )
                ],
            )
            run2 = ExecutionRun(
                run_id="run-2",
                procedure_name="test_proc",
                file_path="/test.tac",
                start_time=datetime.now(timezone.utc),
                status="COMPLETED",
                execution_log=[
                    CheckpointEntry(
                        position=0,
                        type="agent_turn",
                        result={"text": "Hello"},
                        timestamp=datetime.now(timezone.utc),
                        source_location=SourceLocation(file="/test.tac", line=10),
                    )
                ],
            )

            storage.save_run(run1)
            storage.save_run(run2)

            comparison = trace_mgr.compare_runs("run-1", "run-2")

            assert comparison["differences"] == []

    def test_export_trace(self):
        """Test exporting a trace."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = FileStorage(tmpdir)
            trace_mgr = TraceManager(storage)

            # Create run
            run = ExecutionRun(
                run_id="test-run",
                procedure_name="test_proc",
                file_path="/test.tac",
                start_time=datetime.now(timezone.utc),
                status="COMPLETED",
                execution_log=[
                    CheckpointEntry(
                        position=0,
                        type="agent_turn",
                        result={"text": "Hello"},
                        timestamp=datetime.now(timezone.utc),
                    )
                ],
            )
            storage.save_run(run)

            # Export trace
            export_data = trace_mgr.export_trace("test-run", format="json")

            assert "test-run" in export_data
            assert "test_proc" in export_data
            assert "execution_log" in export_data

    def test_get_statistics(self):
        """Test getting run statistics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = FileStorage(tmpdir)
            trace_mgr = TraceManager(storage)

            # Create run with various checkpoint types
            checkpoints = [
                CheckpointEntry(
                    position=0,
                    type="agent_turn",
                    result={},
                    timestamp=datetime.now(timezone.utc),
                    duration_ms=100.0,
                    source_location=SourceLocation(file="/test.tac", line=10),
                ),
                CheckpointEntry(
                    position=1,
                    type="agent_turn",
                    result={},
                    timestamp=datetime.now(timezone.utc),
                    duration_ms=150.0,
                    source_location=SourceLocation(file="/test.tac", line=20),
                ),
                CheckpointEntry(
                    position=2,
                    type="model_predict",
                    result={},
                    timestamp=datetime.now(timezone.utc),
                    duration_ms=50.0,
                ),
            ]

            run = ExecutionRun(
                run_id="test-run",
                procedure_name="test_proc",
                file_path="/test.tac",
                start_time=datetime.now(timezone.utc),
                status="COMPLETED",
                execution_log=checkpoints,
            )
            storage.save_run(run)

            # Get statistics
            stats = trace_mgr.get_statistics("test-run")

            assert stats["total_checkpoints"] == 3
            assert stats["checkpoints_by_type"]["agent_turn"] == 2
            assert stats["checkpoints_by_type"]["model_predict"] == 1
            assert stats["total_duration_ms"] == 300.0
            assert stats["has_source_locations"] == 2

    def test_get_statistics_with_end_time(self):
        """Test statistics with start and end time present."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = FileStorage(tmpdir)
            trace_mgr = TraceManager(storage)

            start_time = datetime.now(timezone.utc)
            end_time = start_time + timedelta(seconds=2)

            run = ExecutionRun(
                run_id="test-run",
                procedure_name="test_proc",
                file_path="/test.tac",
                start_time=start_time,
                end_time=end_time,
                status="COMPLETED",
                execution_log=[],
            )
            storage.save_run(run)

            stats = trace_mgr.get_statistics("test-run")

            assert stats["total_time_sec"] == 2.0

    def test_get_statistics_without_timing(self):
        """Test statistics when timing fields are missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = FileStorage(tmpdir)
            trace_mgr = TraceManager(storage)

            run = ExecutionRun(
                run_id="test-run",
                procedure_name="test_proc",
                file_path="/test.tac",
                start_time=datetime.now(timezone.utc),
                end_time=None,
                status="COMPLETED",
                execution_log=[
                    CheckpointEntry(
                        position=0,
                        type="agent_turn",
                        result={"text": "Hello"},
                        timestamp=datetime.now(timezone.utc),
                        duration_ms=None,
                    )
                ],
            )
            storage.save_run(run)

            stats = trace_mgr.get_statistics("test-run")

            assert stats["total_duration_ms"] == 0.0
            assert stats["total_time_sec"] is None

    def test_list_breakpoints_requires_file(self):
        """Test list_breakpoints requires file parameter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = FileStorage(tmpdir)
            trace_mgr = TraceManager(storage)

            with pytest.raises(NotImplementedError):
                trace_mgr.list_breakpoints()

    def test_list_breakpoints_with_file(self):
        """Test list_breakpoints returns breakpoints for a file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = FileStorage(tmpdir)
            trace_mgr = TraceManager(storage)

            breakpoints = [
                Breakpoint(
                    breakpoint_id="bp-1",
                    file="/test_proc.tac",
                    line=10,
                    enabled=True,
                )
            ]
            storage.save_breakpoints("test_proc", breakpoints)

            result = trace_mgr.list_breakpoints(file="/test_proc.tac")
            assert result == breakpoints

    def test_remove_and_toggle_breakpoint_not_implemented(self):
        """Test remove/toggle breakpoint not implemented."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = FileStorage(tmpdir)
            trace_mgr = TraceManager(storage)

            with pytest.raises(NotImplementedError):
                trace_mgr.remove_breakpoint("bp-1")
            with pytest.raises(NotImplementedError):
                trace_mgr.toggle_breakpoint("bp-1", enabled=False)

    def test_find_checkpoints_by_type(self):
        """Test finding checkpoints by type."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = FileStorage(tmpdir)
            trace_mgr = TraceManager(storage)

            checkpoints = [
                CheckpointEntry(
                    position=0,
                    type="agent_turn",
                    result={},
                    timestamp=datetime.now(timezone.utc),
                ),
                CheckpointEntry(
                    position=1,
                    type="model_predict",
                    result={},
                    timestamp=datetime.now(timezone.utc),
                ),
            ]

            run = ExecutionRun(
                run_id="test-run",
                procedure_name="test_proc",
                file_path="/test.tac",
                start_time=datetime.now(timezone.utc),
                status="COMPLETED",
                execution_log=checkpoints,
            )
            storage.save_run(run)

            matches = trace_mgr.find_checkpoints_by_type("test-run", "model_predict")
            assert len(matches) == 1
            assert matches[0].type == "model_predict"

    def test_compare_runs_checkpoint_count_mismatch(self):
        """Test compare_runs detects count mismatch."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = FileStorage(tmpdir)
            trace_mgr = TraceManager(storage)

            run1 = ExecutionRun(
                run_id="run-1",
                procedure_name="test_proc",
                file_path="/test.tac",
                start_time=datetime.now(timezone.utc),
                status="COMPLETED",
                execution_log=[
                    CheckpointEntry(
                        position=0,
                        type="agent_turn",
                        result={},
                        timestamp=datetime.now(timezone.utc),
                    )
                ],
            )
            run2 = ExecutionRun(
                run_id="run-2",
                procedure_name="test_proc",
                file_path="/test.tac",
                start_time=datetime.now(timezone.utc),
                status="COMPLETED",
                execution_log=[],
            )
            storage.save_run(run1)
            storage.save_run(run2)

            comparison = trace_mgr.compare_runs("run-1", "run-2")
            diffs = [
                d for d in comparison["differences"] if d["type"] == "checkpoint_count_mismatch"
            ]
            assert diffs

    def test_export_trace_rejects_unknown_format(self):
        """Test export_trace with unsupported format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = FileStorage(tmpdir)
            trace_mgr = TraceManager(storage)

            run = ExecutionRun(
                run_id="test-run",
                procedure_name="test_proc",
                file_path="/test.tac",
                start_time=datetime.now(timezone.utc),
                status="COMPLETED",
            )
            storage.save_run(run)

            with pytest.raises(ValueError):
                trace_mgr.export_trace("test-run", format="csv")


class TestExecutionContextTracing:
    """Test execution context with source location capture."""

    def test_checkpoint_captures_source_location(self):
        """Test that checkpoint captures source location."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = FileStorage(tmpdir)
            context = BaseExecutionContext("test-proc", storage)

            # Create a simple function to checkpoint
            def test_function():
                return "test_result"

            # Capture source info manually (simulating what primitives do)
            import inspect

            frame = inspect.currentframe()
            source_info = {
                "file": frame.f_code.co_filename,
                "line": frame.f_lineno,
                "function": frame.f_code.co_name,
            }

            # Execute checkpoint with source info
            result = context.checkpoint(test_function, "test_checkpoint", source_info=source_info)

            assert result == "test_result"
            assert len(context.metadata.execution_log) == 1

            checkpoint = context.metadata.execution_log[0]
            assert checkpoint.source_location is not None
            assert checkpoint.source_location.file.endswith("test_tracing.py")
            assert checkpoint.source_location.function == "test_checkpoint_captures_source_location"

    def test_checkpoint_replay_with_source_location(self):
        """Test that checkpoint preserves source location across multiple checkpoints."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = FileStorage(tmpdir)

            # Create context and execute multiple checkpoints
            context = BaseExecutionContext("test-proc", storage)

            import inspect

            # First checkpoint
            frame1 = inspect.currentframe()
            source_info1 = {
                "file": frame1.f_code.co_filename,
                "line": frame1.f_lineno,
                "function": frame1.f_code.co_name,
            }

            result1 = context.checkpoint(
                lambda: "result1", "test_checkpoint_1", source_info=source_info1
            )
            assert result1 == "result1"

            # Second checkpoint with different line
            frame2 = inspect.currentframe()
            source_info2 = {
                "file": frame2.f_code.co_filename,
                "line": frame2.f_lineno,  # Different line than first checkpoint
                "function": frame2.f_code.co_name,
            }

            result2 = context.checkpoint(
                lambda: "result2", "test_checkpoint_2", source_info=source_info2
            )
            assert result2 == "result2"

            # Verify both checkpoints have source locations
            assert len(context.metadata.execution_log) == 2
            assert context.metadata.execution_log[0].source_location is not None
            assert context.metadata.execution_log[1].source_location is not None

            # Verify source locations are different
            assert (
                context.metadata.execution_log[0].source_location.line
                != context.metadata.execution_log[1].source_location.line
            )

            # Reload metadata from storage to verify persistence
            context2 = BaseExecutionContext("test-proc", storage)
            assert len(context2.metadata.execution_log) == 2
            assert context2.metadata.execution_log[0].source_location is not None
            assert context2.metadata.execution_log[1].source_location is not None
