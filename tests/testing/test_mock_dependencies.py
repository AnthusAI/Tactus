"""Tests for mock dependency implementations."""

import asyncio

from tactus.testing.mock_dependencies import (
    MockHTTPClient,
    MockDatabase,
    MockRedis,
    MockDependencyFactory,
)


def test_mock_http_client_get_and_post():
    client = MockHTTPClient({"/path": '{"ok": true}'})

    response = asyncio.run(client.get("/path"))
    assert response.status_code == 200
    assert response.json() == {"ok": True}

    response = asyncio.run(client.post("/other"))
    assert response.status_code == 200
    assert response.text == "{}"
    assert client.was_called(method="POST", path="/other")


def test_mock_database_exec_and_fetch():
    db = MockDatabase()
    asyncio.run(db.execute("SELECT 1"))
    rows = asyncio.run(db.fetch("SELECT 1"))

    assert rows == []
    assert "SELECT 1" in db.queries


def test_mock_redis_set_get_delete():
    redis = MockRedis()
    asyncio.run(redis.set("key", "value"))

    assert asyncio.run(redis.get("key")) == "value"

    asyncio.run(redis.delete("key"))
    assert asyncio.run(redis.get("key")) is None


def test_mock_dependency_factory_creates_resources():
    http = asyncio.run(
        MockDependencyFactory.create_mock("http_client", {"base_url": "http://example.com"})
    )
    db = asyncio.run(MockDependencyFactory.create_mock("postgres", {}))
    cache = asyncio.run(MockDependencyFactory.create_mock("redis", {}))

    assert isinstance(http, MockHTTPClient)
    assert isinstance(db, MockDatabase)
    assert isinstance(cache, MockRedis)


def test_mock_dependency_factory_create_all():
    deps = {
        "api": {"type": "http_client", "base_url": "http://example.com"},
        "db": {"type": "postgres"},
    }
    mocks = asyncio.run(MockDependencyFactory.create_all_mocks(deps))

    assert "api" in mocks
    assert "db" in mocks
