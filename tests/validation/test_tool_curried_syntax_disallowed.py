from __future__ import annotations

import pytest

from tactus.adapters.memory import MemoryStorage
from tactus.core import TactusRuntime
from tactus.validation import TactusValidator, ValidationMode


def test_validator_rejects_curried_tool_syntax():
    source = """
Tool "my_tool" {
  description = "Nope",
  function(_)
    return 1
  end
}

Procedure {
  output = { ok = field.boolean{required = true} },
  function(_)
    return { ok = true }
  end
}
"""

    result = TactusValidator().validate(source, mode=ValidationMode.FULL)
    assert result.valid is False
    assert any("Curried Tool syntax is not supported" in e.message for e in result.errors)


@pytest.mark.asyncio
async def test_runtime_errors_on_curried_tool_syntax():
    source = """
Tool "my_tool" {
  description = "Nope",
  function(_)
    return 1
  end
}

Procedure {
  output = { ok = field.boolean{required = true} },
  function(_)
    return { ok = true }
  end
}
"""

    runtime = TactusRuntime(
        procedure_id="test-curried-tool-disallowed",
        storage_backend=MemoryStorage(),
    )

    result = await runtime.execute(source=source, context={}, format="lua")
    assert result.get("success") is False
    assert "Curried Tool syntax is not supported" in result.get("error", "")
