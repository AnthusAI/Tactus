import pytest

from tactus.core.runtime import TactusRuntime


class DummyLua:
    def __init__(self):
        self._globals = {}

    def globals(self):
        return self._globals


class DummyLuaSandbox:
    def __init__(self):
        self.lua = DummyLua()


class DummyProcedureCallable:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


@pytest.mark.asyncio
async def test_initialize_named_procedures_updates_stub(monkeypatch):
    runtime = TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.registry = type(
        "Registry",
        (),
        {
            "named_procedures": {
                "do_work": {
                    "function": lambda: None,
                    "input_schema": {},
                    "output_schema": {},
                    "state_schema": {},
                }
            }
        },
    )()
    runtime.lua_sandbox = DummyLuaSandbox()
    runtime.execution_context = object()

    stub = type("Stub", (), {"registry": {}})()
    runtime.lua_sandbox.lua.globals()["do_work"] = stub

    monkeypatch.setattr(
        "tactus.primitives.procedure_callable.ProcedureCallable", DummyProcedureCallable
    )

    await runtime._initialize_named_procedures()

    assert "do_work" in stub.registry
    assert runtime.lua_sandbox.lua.globals()["do_work"].kwargs["name"] == "do_work"


@pytest.mark.asyncio
async def test_initialize_named_procedures_without_stub(monkeypatch):
    runtime = TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.registry = type(
        "Registry",
        (),
        {
            "named_procedures": {
                "do_work": {
                    "function": lambda: None,
                    "input_schema": {},
                    "output_schema": {},
                    "state_schema": {},
                }
            }
        },
    )()
    runtime.lua_sandbox = DummyLuaSandbox()
    runtime.execution_context = object()

    monkeypatch.setattr(
        "tactus.primitives.procedure_callable.ProcedureCallable", DummyProcedureCallable
    )

    await runtime._initialize_named_procedures()

    assert runtime.lua_sandbox.lua.globals()["do_work"].kwargs["name"] == "do_work"


@pytest.mark.asyncio
async def test_initialize_named_procedures_handles_error(monkeypatch):
    runtime = TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.registry = type(
        "Registry",
        (),
        {
            "named_procedures": {
                "boom": {
                    "function": lambda: None,
                    "input_schema": {},
                    "output_schema": {},
                    "state_schema": {},
                }
            }
        },
    )()
    runtime.lua_sandbox = DummyLuaSandbox()
    runtime.execution_context = object()

    class FailingCallable:
        def __init__(self, **kwargs):
            raise RuntimeError("boom")

    monkeypatch.setattr("tactus.primitives.procedure_callable.ProcedureCallable", FailingCallable)

    await runtime._initialize_named_procedures()
