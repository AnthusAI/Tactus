import pytest

from tactus.protocols.models import ExecutionRun, CheckpointEntry, Breakpoint, utc_now
from tactus.tracing.trace_manager import TraceManager


class DummyStorage:
    def __init__(self, runs=None):
        self._runs = runs or {}
        self.breakpoints = {}

    def list_runs(self, procedure_name=None):
        runs = list(self._runs.values())
        if procedure_name:
            runs = [r for r in runs if r.procedure_name == procedure_name]
        return runs

    def load_run(self, run_id):
        return self._runs[run_id]

    def load_breakpoints(self, procedure_name):
        return self.breakpoints.get(procedure_name, [])

    def save_breakpoints(self, procedure_name, breakpoints):
        self.breakpoints[procedure_name] = breakpoints


def test_get_checkpoint_out_of_range():
    run = ExecutionRun(
        run_id="run",
        procedure_name="proc",
        file_path="proc.tac",
        start_time=utc_now(),
        status="COMPLETED",
        execution_log=[CheckpointEntry(position=0, type="tool", result=None, timestamp=utc_now())],
    )
    storage = DummyStorage(runs={"run": run})
    manager = TraceManager(storage)

    with pytest.raises(IndexError):
        manager.get_checkpoint("run", 2)


def test_get_checkpoints_end_none_returns_all():
    run = ExecutionRun(
        run_id="run",
        procedure_name="proc",
        file_path="proc.tac",
        start_time=utc_now(),
        status="COMPLETED",
        execution_log=[
            CheckpointEntry(position=0, type="tool", result=None, timestamp=utc_now()),
            CheckpointEntry(position=1, type="tool", result=None, timestamp=utc_now()),
        ],
    )
    storage = DummyStorage(runs={"run": run})
    manager = TraceManager(storage)

    checkpoints = manager.get_checkpoints("run")
    assert len(checkpoints) == 2


def test_set_breakpoint_persists_to_storage(tmp_path):
    storage = DummyStorage()
    manager = TraceManager(storage)

    bp = manager.set_breakpoint(str(tmp_path / "proc.tac"), 10)

    assert isinstance(bp, Breakpoint)
    assert storage.breakpoints["proc"][0].line == 10
