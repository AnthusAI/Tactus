from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from tactus.cli import app as cli_app


@pytest.fixture
def cli_runner():
    return CliRunner()


class FakeTraceManager:
    def __init__(self, storage):
        self.storage = storage
        now = datetime.now(timezone.utc)
        self.run = SimpleNamespace(
            run_id="run-1234567890",
            procedure_name="proc",
            status="COMPLETED",
            start_time=now,
            end_time=now + timedelta(seconds=1),
            execution_log=[
                SimpleNamespace(
                    position=0,
                    type="agent_turn",
                    duration_ms=12.0,
                    source_location=SimpleNamespace(file="file.tac", line=10, function=None),
                )
            ],
            file_path="file.tac",
        )

    def list_runs(self, procedure_name=None, limit=20):
        if procedure_name == "empty":
            return []
        return [self.run]

    def get_run(self, run_id):
        if run_id != "run-1234567890":
            raise FileNotFoundError(run_id)
        return self.run

    def get_checkpoint(self, run_id, position):
        if position != 0:
            raise IndexError(position)
        return SimpleNamespace(
            type="agent_turn",
            timestamp=datetime.now(timezone.utc),
            duration_ms=5.0,
            source_location=SimpleNamespace(
                file="file.tac", line=10, function="main", code_context=None
            ),
            captured_vars='{"ok": true}',
            result='{"done": true}',
        )

    def get_statistics(self, run_id):
        return {
            "total_duration_ms": 12.0,
            "has_source_locations": 1,
            "checkpoints_by_type": {"agent_turn": 1},
        }

    def export_trace(self, run_id, fmt):
        if fmt != "json":
            raise ValueError("unsupported format")
        if run_id != "run-1234567890":
            raise FileNotFoundError(run_id)
        return '{"ok": true}'


class FakeTraceManagerRunning(FakeTraceManager):
    def __init__(self, storage):
        super().__init__(storage)
        self.run = SimpleNamespace(
            run_id="run-running",
            procedure_name="proc",
            status="RUNNING",
            start_time=self.run.start_time,
            end_time=None,
            execution_log=[],
            file_path="file.tac",
        )

    def get_run(self, run_id):
        if run_id != "run-running":
            raise FileNotFoundError(run_id)
        return self.run


class FakeTraceManagerNoSource(FakeTraceManager):
    def __init__(self, storage):
        super().__init__(storage)
        self.run = SimpleNamespace(
            run_id="run-nosource",
            procedure_name="proc",
            status="COMPLETED",
            start_time=self.run.start_time,
            end_time=self.run.end_time,
            execution_log=[
                SimpleNamespace(
                    position=0,
                    type="agent_turn",
                    duration_ms=None,
                    source_location=None,
                )
            ],
            file_path="file.tac",
        )

    def get_run(self, run_id):
        if run_id != "run-nosource":
            raise FileNotFoundError(run_id)
        return self.run


class FakeTraceManagerWithCode(FakeTraceManager):
    def get_checkpoint(self, run_id, position):
        return SimpleNamespace(
            type="agent_turn",
            timestamp=datetime.now(timezone.utc),
            duration_ms=None,
            source_location=SimpleNamespace(
                file="file.tac",
                line=10,
                function="main",
                code_context="print('hi')",
            ),
            captured_vars='{"ok": true}',
            result='{"done": true}',
        )


class FakeTraceManagerNoFunction(FakeTraceManager):
    def get_checkpoint(self, run_id, position):
        return SimpleNamespace(
            type="agent_turn",
            timestamp=datetime.now(timezone.utc),
            duration_ms=5.0,
            source_location=SimpleNamespace(
                file="file.tac", line=10, function=None, code_context=None
            ),
            captured_vars=None,
            result='{"done": true}',
        )


class FakeTraceManagerNoSource(FakeTraceManager):  # noqa: F811
    def __init__(self, storage):
        super().__init__(storage)
        self.run = SimpleNamespace(
            run_id="run-nosource",
            procedure_name="proc",
            status="COMPLETED",
            start_time=self.run.start_time,
            end_time=self.run.end_time,
            execution_log=[
                SimpleNamespace(
                    position=0,
                    type="agent_turn",
                    duration_ms=None,
                    source_location=None,
                )
            ],
            file_path="file.tac",
        )

    def get_run(self, run_id):
        if run_id != "run-nosource":
            raise FileNotFoundError(run_id)
        return self.run

    def get_checkpoint(self, run_id, position):
        return SimpleNamespace(
            type="agent_turn",
            timestamp=datetime.now(timezone.utc),
            duration_ms=5.0,
            source_location=None,
            captured_vars=None,
            result='{"done": true}',
        )


class ExplodingTraceManager(FakeTraceManager):
    def list_runs(self, procedure_name=None, limit=20):
        raise RuntimeError("boom")


def test_trace_list_outputs_table(monkeypatch, cli_runner, tmp_path):
    monkeypatch.setattr("tactus.tracing.TraceManager", FakeTraceManager)
    result = cli_runner.invoke(cli_app.app, ["trace-list", "--storage-path", str(tmp_path)])
    assert result.exit_code == 0
    assert "Execution Traces" in result.stdout


def test_trace_list_default_storage(monkeypatch, cli_runner):
    monkeypatch.setattr("tactus.tracing.TraceManager", FakeTraceManager)
    result = cli_runner.invoke(cli_app.app, ["trace-list"])
    assert result.exit_code == 0


def test_trace_list_no_runs(monkeypatch, cli_runner, tmp_path):
    monkeypatch.setattr("tactus.tracing.TraceManager", FakeTraceManager)
    result = cli_runner.invoke(
        cli_app.app, ["trace-list", "--procedure", "empty", "--storage-path", str(tmp_path)]
    )
    assert result.exit_code == 0
    assert "No execution traces found" in result.stdout


def test_trace_list_filters_status(monkeypatch, cli_runner, tmp_path):
    monkeypatch.setattr("tactus.tracing.TraceManager", FakeTraceManager)
    result = cli_runner.invoke(
        cli_app.app,
        ["trace-list", "--status", "FAILED", "--storage-path", str(tmp_path)],
    )
    assert result.exit_code == 0
    assert "No execution traces found" in result.stdout


def test_trace_list_running_duration(monkeypatch, cli_runner, tmp_path):
    monkeypatch.setattr("tactus.tracing.TraceManager", FakeTraceManagerRunning)
    result = cli_runner.invoke(cli_app.app, ["trace-list", "--storage-path", str(tmp_path)])
    assert result.exit_code == 0
    assert "running..." in result.stdout


def test_trace_list_handles_error(monkeypatch, cli_runner, tmp_path):
    monkeypatch.setattr("tactus.tracing.TraceManager", ExplodingTraceManager)
    result = cli_runner.invoke(cli_app.app, ["trace-list", "--storage-path", str(tmp_path)])
    assert result.exit_code == 1


def test_trace_show_summary(monkeypatch, cli_runner, tmp_path):
    monkeypatch.setattr("tactus.tracing.TraceManager", FakeTraceManager)
    result = cli_runner.invoke(
        cli_app.app, ["trace-show", "run-1234567890", "--storage-path", str(tmp_path)]
    )
    assert result.exit_code == 0
    assert "Execution Trace" in result.stdout


def test_trace_show_summary_default_storage(monkeypatch, cli_runner):
    monkeypatch.setattr("tactus.tracing.TraceManager", FakeTraceManager)
    result = cli_runner.invoke(cli_app.app, ["trace-show", "run-1234567890"])
    assert result.exit_code == 0


def test_trace_show_summary_running(monkeypatch, cli_runner, tmp_path):
    monkeypatch.setattr("tactus.tracing.TraceManager", FakeTraceManagerRunning)
    result = cli_runner.invoke(
        cli_app.app, ["trace-show", "run-running", "--storage-path", str(tmp_path)]
    )
    assert result.exit_code == 0


def test_trace_show_summary_without_source(monkeypatch, cli_runner, tmp_path):
    monkeypatch.setattr("tactus.tracing.TraceManager", FakeTraceManagerNoSource)
    result = cli_runner.invoke(
        cli_app.app, ["trace-show", "run-nosource", "--storage-path", str(tmp_path)]
    )
    assert result.exit_code == 0


def test_trace_show_checkpoint(monkeypatch, cli_runner, tmp_path):
    monkeypatch.setattr("tactus.tracing.TraceManager", FakeTraceManager)
    result = cli_runner.invoke(
        cli_app.app,
        [
            "trace-show",
            "run-1234567890",
            "--position",
            "0",
            "--storage-path",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0
    assert "Checkpoint 0" in result.stdout


def test_trace_show_checkpoint_with_code_context(monkeypatch, cli_runner, tmp_path):
    monkeypatch.setattr("tactus.tracing.TraceManager", FakeTraceManagerWithCode)
    result = cli_runner.invoke(
        cli_app.app,
        [
            "trace-show",
            "run-1234567890",
            "--position",
            "0",
            "--storage-path",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0
    assert "Code Context" in result.stdout


def test_trace_show_checkpoint_without_function(monkeypatch, cli_runner, tmp_path):
    monkeypatch.setattr("tactus.tracing.TraceManager", FakeTraceManagerNoFunction)
    result = cli_runner.invoke(
        cli_app.app,
        [
            "trace-show",
            "run-1234567890",
            "--position",
            "0",
            "--storage-path",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0


def test_trace_show_checkpoint_without_source(monkeypatch, cli_runner, tmp_path):
    monkeypatch.setattr("tactus.tracing.TraceManager", FakeTraceManagerNoSource)
    result = cli_runner.invoke(
        cli_app.app,
        [
            "trace-show",
            "run-nosource",
            "--position",
            "0",
            "--storage-path",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0


def test_trace_export_writes_file(monkeypatch, cli_runner, tmp_path):
    monkeypatch.setattr("tactus.tracing.TraceManager", FakeTraceManager)
    output_path = tmp_path / "trace.json"
    result = cli_runner.invoke(
        cli_app.app,
        ["trace-export", "run-1234567890", str(output_path), "--storage-path", str(tmp_path)],
    )
    assert result.exit_code == 0


def test_trace_show_handles_error(monkeypatch, cli_runner, tmp_path):
    class ExplodingTraceManagerShow(FakeTraceManager):
        def get_run(self, run_id):
            raise RuntimeError("boom")

    monkeypatch.setattr("tactus.tracing.TraceManager", ExplodingTraceManagerShow)
    result = cli_runner.invoke(
        cli_app.app, ["trace-show", "run-1234567890", "--storage-path", str(tmp_path)]
    )
    assert result.exit_code == 1


def test_trace_export_handles_unexpected_error(monkeypatch, cli_runner, tmp_path):
    class ExplodingTraceManagerExport(FakeTraceManager):
        def export_trace(self, run_id, fmt):
            raise RuntimeError("boom")

    monkeypatch.setattr("tactus.tracing.TraceManager", ExplodingTraceManagerExport)
    output_path = tmp_path / "trace.json"
    result = cli_runner.invoke(cli_app.app, ["trace-export", "run-1234567890", str(output_path)])
    assert result.exit_code == 1


def test_trace_show_not_found(monkeypatch, cli_runner, tmp_path):
    monkeypatch.setattr("tactus.tracing.TraceManager", FakeTraceManager)
    result = cli_runner.invoke(
        cli_app.app, ["trace-show", "missing", "--storage-path", str(tmp_path)]
    )
    assert result.exit_code == 1
    assert "not found" in result.stdout.lower()


def test_trace_show_checkpoint_out_of_range(monkeypatch, cli_runner, tmp_path):
    monkeypatch.setattr("tactus.tracing.TraceManager", FakeTraceManager)
    result = cli_runner.invoke(
        cli_app.app,
        [
            "trace-show",
            "run-1234567890",
            "--position",
            "1",
            "--storage-path",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 1
    assert "out of range" in result.stdout.lower()


def test_trace_export_invalid_format(monkeypatch, cli_runner, tmp_path):
    monkeypatch.setattr("tactus.tracing.TraceManager", FakeTraceManager)
    result = cli_runner.invoke(
        cli_app.app,
        ["trace-export", "run-1234567890", str(tmp_path / "out.txt"), "--format", "csv"],
    )
    assert result.exit_code == 1
    assert "error" in result.stdout.lower()


def test_trace_export_missing_run(monkeypatch, cli_runner, tmp_path):
    monkeypatch.setattr("tactus.tracing.TraceManager", FakeTraceManager)
    result = cli_runner.invoke(
        cli_app.app,
        ["trace-export", "missing", str(tmp_path / "out.json"), "--storage-path", str(tmp_path)],
    )
    assert result.exit_code == 1
    assert "not found" in result.stdout.lower()
