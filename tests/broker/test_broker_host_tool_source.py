from __future__ import annotations

import pytest

from tactus.adapters.memory import MemoryStorage
from tactus.core import TactusRuntime


@pytest.mark.asyncio
async def test_tool_use_broker_host_executes_allowlisted_host_tool(monkeypatch):
    monkeypatch.delenv("TACTUS_BROKER_SOCKET", raising=False)

    source = """
host_ping = Tool {
  use = "broker.host.ping"
}

Procedure {
  output = {
    ok = field.boolean{required = true},
    echo = field.object{required = true},
  },
  function(_)
    local result = host_ping({x = 1})
    return { ok = result.ok, echo = result.echo }
  end
}
"""

    runtime = TactusRuntime(
        procedure_id="test-broker-host-tool-source",
        storage_backend=MemoryStorage(),
    )

    result = await runtime.execute(source=source, context={}, format="lua")
    assert result.get("success") is True
    assert result.get("result") == {"ok": True, "echo": {"x": 1}}

    assert runtime.tool_primitive.called("host_ping") is True
