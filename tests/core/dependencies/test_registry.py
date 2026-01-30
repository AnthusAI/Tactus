"""Tests for dependency registry and resource manager."""

import asyncio
import builtins
import sys

import pytest

from tactus.core.dependencies.registry import ResourceFactory, ResourceManager, ResourceType


class FakeResource:
    def __init__(self):
        self.closed = False

    async def aclose(self):
        self.closed = True


class FakePool:
    def __init__(self):
        self.closed = False
        self.waited = False

    async def close(self):
        self.closed = True

    async def wait_closed(self):
        self.waited = True


class FakeRedis:
    def __init__(self):
        self.closed = False

    async def close(self):
        self.closed = True


def test_resource_factory_create_unknown():
    with pytest.raises(ValueError):
        asyncio.run(ResourceFactory.create("unknown", {}))


def test_resource_factory_create_known_types(monkeypatch):
    async def fake_http(_config):
        return "http"

    async def fake_pg(_config):
        return "pg"

    async def fake_redis(_config):
        return "redis"

    monkeypatch.setattr(ResourceFactory, "_create_http_client", fake_http)
    monkeypatch.setattr(ResourceFactory, "_create_postgres", fake_pg)
    monkeypatch.setattr(ResourceFactory, "_create_redis", fake_redis)

    assert asyncio.run(ResourceFactory.create(ResourceType.HTTP_CLIENT.value, {})) == "http"
    assert asyncio.run(ResourceFactory.create(ResourceType.POSTGRES.value, {})) == "pg"
    assert asyncio.run(ResourceFactory.create(ResourceType.REDIS.value, {})) == "redis"


def test_resource_factory_create_all_missing_type():
    with pytest.raises(ValueError):
        asyncio.run(ResourceFactory.create_all({"dep": {}}))


def test_resource_manager_cleanup():
    manager = ResourceManager()

    http = FakeResource()
    pool = FakePool()
    redis = FakeRedis()
    other = object()

    asyncio.run(manager.add_resource("http", http))
    asyncio.run(manager.add_resource("pool", pool))
    asyncio.run(manager.add_resource("redis", redis))
    asyncio.run(manager.add_resource("other", other))

    asyncio.run(manager.cleanup())

    assert http.closed is True
    assert pool.closed is True
    assert pool.waited is True
    assert redis.closed is True


def test_resource_manager_cleanup_unknown_resource_logs(caplog):
    manager = ResourceManager()
    asyncio.run(manager.add_resource("unknown", object()))
    asyncio.run(manager.cleanup())
    assert any("Unknown resource type" in record.message for record in caplog.records)


def test_resource_manager_cleanup_logs_errors(caplog):
    manager = ResourceManager()

    class BrokenResource:
        async def aclose(self):
            raise RuntimeError("boom")

    asyncio.run(manager.add_resource("broken", BrokenResource()))
    asyncio.run(manager.cleanup())

    assert any("Error cleaning up resource" in record.message for record in caplog.records)


def test_resource_factory_create_http_client_missing_dep(monkeypatch):
    original_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "httpx":
            raise ImportError("no httpx")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(ImportError):
        asyncio.run(ResourceFactory._create_http_client({"base_url": "https://example.com"}))


def test_resource_factory_create_http_client_success(monkeypatch):
    class FakeClient:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    fake_httpx = type("httpx", (), {"AsyncClient": FakeClient})
    monkeypatch.setitem(sys.modules, "httpx", fake_httpx)

    client = asyncio.run(
        ResourceFactory._create_http_client(
            {"base_url": "https://example.com", "headers": {"x": "y"}, "timeout": 5.0}
        )
    )

    assert client.kwargs["base_url"] == "https://example.com"
    assert client.kwargs["headers"] == {"x": "y"}
    assert client.kwargs["timeout"] == 5.0


def test_resource_factory_create_postgres_missing_dep(monkeypatch):
    original_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "asyncpg":
            raise ImportError("no asyncpg")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(ImportError):
        asyncio.run(ResourceFactory._create_postgres({"connection_string": "postgres://x"}))


def test_resource_factory_create_postgres_success(monkeypatch):
    async def fake_create_pool(_conn, min_size=None, max_size=None):
        return {"conn": _conn, "min": min_size, "max": max_size}

    fake_asyncpg = type("asyncpg", (), {"create_pool": fake_create_pool})
    monkeypatch.setitem(sys.modules, "asyncpg", fake_asyncpg)

    pool = asyncio.run(
        ResourceFactory._create_postgres(
            {"connection_string": "postgres://x", "pool_size": 2, "max_pool_size": 3}
        )
    )

    assert pool["conn"] == "postgres://x"
    assert pool["min"] == 2
    assert pool["max"] == 3


def test_resource_factory_create_redis_missing_dep(monkeypatch):
    original_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "redis.asyncio":
            raise ImportError("no redis")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(ImportError):
        asyncio.run(ResourceFactory._create_redis({"url": "redis://localhost"}))


def test_resource_factory_create_redis_success(monkeypatch):
    class FakeRedisModule:
        def __init__(self):
            self.called = False

        def from_url(self, url, encoding=None, decode_responses=None):
            self.called = True
            return {"url": url, "encoding": encoding, "decode": decode_responses}

    fake_redis = FakeRedisModule()
    monkeypatch.setitem(sys.modules, "redis.asyncio", fake_redis)
    monkeypatch.setitem(sys.modules, "redis", type("redis", (), {"asyncio": fake_redis}))

    client = asyncio.run(ResourceFactory._create_redis({"url": "redis://localhost"}))
    assert client["url"] == "redis://localhost"
    assert client["encoding"] == "utf-8"
    assert client["decode"] is True


def test_resource_factory_create_all_success(monkeypatch):
    async def fake_create(resource_type, config):
        return {"type": resource_type, "config": config}

    monkeypatch.setattr(ResourceFactory, "create", fake_create)

    resources = asyncio.run(
        ResourceFactory.create_all(
            {"dep": {"type": ResourceType.HTTP_CLIENT.value, "base_url": "https://x"}}
        )
    )

    assert resources["dep"]["type"] == ResourceType.HTTP_CLIENT.value
