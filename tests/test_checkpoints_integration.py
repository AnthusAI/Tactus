"""
Integration test for checkpoint + tracing persistence.

This intentionally avoids network and API keys by running a minimal procedure
that creates an explicit checkpoint via the `checkpoint(fn)` helper.
"""

from pathlib import Path

import pytest

from tactus.adapters.file_storage import FileStorage
from tactus.core import TactusRuntime


@pytest.mark.integration
@pytest.mark.asyncio
async def test_integration(tmp_path: Path) -> None:
    source = """
Procedure {
    input = {
        value = field.number{default = 2}
    },
    output = {
        result = field.number{required = true}
    },
    function(input)
        local doubled = checkpoint(function()
            return input.value * 2
        end)

        return {
            result = doubled
        }
    end
}
""".strip()

    storage = FileStorage(storage_dir=str(tmp_path / "tactus-storage"))
    runtime = TactusRuntime(
        procedure_id="checkpoint_test",
        storage_backend=storage,
        source_file_path=str((tmp_path / "inline.tac").resolve()),
    )

    result = await runtime.execute(source, context={}, format="lua")
    assert result.get("success") is True
    assert result.get("result") == {"result": 4.0}
    assert runtime.execution_context is not None

    run_id = runtime.execution_context.save_execution_run(
        procedure_name="checkpoint_test",
        file_path=str((tmp_path / "inline.tac").resolve()),
        status="COMPLETED",
    )

    loaded_run = storage.load_run(run_id)
    assert loaded_run.run_id == run_id
    assert len(loaded_run.execution_log) >= 1
