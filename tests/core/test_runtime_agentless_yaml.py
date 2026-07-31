"""Runtime contracts for orchestration-only legacy YAML procedures."""

import pytest

from tactus.adapters.memory import MemoryStorage
from tactus.core.runtime import TactusRuntime
from tactus.testing.mock_hitl import MockHITLHandler


@pytest.mark.asyncio
async def test_agentless_yaml_can_orchestrate_host_state_and_hitl():
    source = """
name: Agentless orchestration
version: 1.0.0
procedure: |
  State.set("phase", "approval")
  local ping = Host.call("host.ping", {stage = State.get("phase")})
  local approved = Human.approve({message = "Continue?"})
  return {
    approved = approved,
    phase = State.get("phase"),
    host_ok = ping.ok
  }
"""
    hitl = MockHITLHandler()
    runtime = TactusRuntime(
        procedure_id="agentless-orchestration",
        storage_backend=MemoryStorage(),
        hitl_handler=hitl,
    )

    result = await runtime.execute(source, format="yaml")

    assert result["success"] is True
    assert result["result"] == {
        "approved": True,
        "phase": "approval",
        "host_ok": True,
    }
    assert len(hitl.requests_received) == 1


@pytest.mark.asyncio
async def test_agentless_yaml_still_rejects_an_undeclared_agent_reference():
    source = """
name: Invalid orchestration
version: 1.0.0
procedure: |
  local result = missing_agent({message = "This must not run"})
  return {result = result}
"""
    runtime = TactusRuntime(
        procedure_id="invalid-agent-reference",
        storage_backend=MemoryStorage(),
    )

    result = await runtime.execute(source, format="yaml")

    assert result["success"] is False
    assert "missing_agent" in result["error"]
    assert "nil value" in result["error"]
