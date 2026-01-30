from types import SimpleNamespace

import pytest

from tactus.core.runtime import TactusRuntime


class DummyDependency:
    def __init__(self, config):
        self.config = config


@pytest.mark.asyncio
async def test_initialize_dependencies_no_registry():
    runtime = TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.registry = None

    await runtime._initialize_dependencies()

    assert runtime.user_dependencies == {}
    assert runtime.dependency_manager is None


@pytest.mark.asyncio
async def test_initialize_dependencies_success(monkeypatch):
    runtime = TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.registry = SimpleNamespace(dependencies={"db": DummyDependency({"url": "sqlite://"})})

    class DummyManager:
        def __init__(self):
            self.added = []

        async def add_resource(self, name, resource):
            self.added.append((name, resource))

    async def fake_create_all(config):
        assert "db" in config
        return {"db": object()}

    monkeypatch.setattr("tactus.core.dependencies.ResourceFactory.create_all", fake_create_all)
    monkeypatch.setattr("tactus.core.dependencies.ResourceManager", DummyManager)

    await runtime._initialize_dependencies()

    assert "db" in runtime.user_dependencies
    assert runtime.dependency_manager.added


@pytest.mark.asyncio
async def test_initialize_dependencies_failure(monkeypatch):
    runtime = TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.registry = SimpleNamespace(dependencies={"db": DummyDependency({"url": "sqlite://"})})

    async def fake_create_all(_config):
        raise RuntimeError("boom")

    monkeypatch.setattr("tactus.core.dependencies.ResourceFactory.create_all", fake_create_all)
    monkeypatch.setattr("tactus.core.dependencies.ResourceManager", lambda: object())

    with pytest.raises(RuntimeError, match="Dependency initialization failed: boom"):
        await runtime._initialize_dependencies()
