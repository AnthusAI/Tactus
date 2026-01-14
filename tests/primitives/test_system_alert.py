import pytest

from tactus.adapters.memory import MemoryStorage
from tactus.core.runtime import TactusRuntime


class CaptureLogHandler:
    def __init__(self):
        self.events = []

    def log(self, event) -> None:
        self.events.append(event)


@pytest.mark.asyncio
async def test_system_alert_emits_structured_event():
    source = """
    main = Procedure("main", {
        input = {},
        output = {ok = {type = "boolean"}}
    }, function()
        System.alert({
            message = "Memory usage high",
            level = "warning",
            source = "unit_test",
            context = {memory_mb = 1500}
        })
        return {ok = true}
    end)
    """

    handler = CaptureLogHandler()
    runtime = TactusRuntime(
        procedure_id="test-system-alert",
        storage_backend=MemoryStorage(),
        log_handler=handler,
    )

    result = await runtime.execute(source=source, context={}, format="lua")
    assert result["success"] is True

    from tactus.protocols.models import SystemAlertEvent

    alerts = [e for e in handler.events if isinstance(e, SystemAlertEvent)]
    assert len(alerts) == 1
    assert alerts[0].level == "warning"
    assert alerts[0].message == "Memory usage high"
    assert alerts[0].source == "unit_test"
    assert alerts[0].context == {"memory_mb": 1500}


@pytest.mark.asyncio
async def test_system_alert_rejects_invalid_level():
    source = """
    main = Procedure("main", {
        input = {},
        output = {ok = {type = "boolean"}}
    }, function()
        System.alert({message = "Bad level", level = "nope"})
        return {ok = true}
    end)
    """

    runtime = TactusRuntime(
        procedure_id="test-system-alert-invalid",
        storage_backend=MemoryStorage(),
    )

    result = await runtime.execute(source=source, context={}, format="lua")
    assert result["success"] is False
    assert "Invalid alert level" in result.get("error", "")
