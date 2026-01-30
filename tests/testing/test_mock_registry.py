"""Tests for unified mock registry and dependency mocks."""

import asyncio

from tactus.testing.mock_registry import UnifiedMockRegistry
from tactus.testing.mock_dependencies import MockHTTPClient
from tactus.testing.mock_hitl import MockHITLHandler


def test_configure_http_response_default():
    registry = UnifiedMockRegistry()
    registry.configure_http_response("api", None, "{}")

    assert "api" in registry.http_mocks
    assert registry.http_mocks["api"].responses["_default"]["text"] == "{}"


def test_configure_http_response_with_path():
    registry = UnifiedMockRegistry()
    registry.configure_http_response("api", "/status", '{"ok": true}', status_code=201)

    assert registry.http_mocks["api"].responses["/status"]["status_code"] == 201


def test_configure_http_response_reuses_existing_client():
    registry = UnifiedMockRegistry()
    registry.configure_http_response("api", "/status", '{"ok": true}')
    existing = registry.http_mocks["api"]

    registry.configure_http_response("api", "/other", '{"ok": false}')

    assert registry.http_mocks["api"] is existing


def test_create_mock_dependencies():
    registry = UnifiedMockRegistry()
    deps = {
        "api": {"type": "http_client", "base_url": "http://example.com"},
        "db": {"type": "postgres"},
        "cache": {"type": "redis"},
    }

    mocks = asyncio.run(registry.create_mock_dependencies(deps))

    assert isinstance(mocks["api"], MockHTTPClient)
    assert mocks["api"].base_url == "http://example.com"
    assert "db" in mocks
    assert "cache" in mocks
    assert registry.get_mock("api") is mocks["api"]


def test_create_mock_dependencies_reuses_existing_mocks():
    registry = UnifiedMockRegistry()
    deps = {
        "db": {"type": "postgres"},
        "cache": {"type": "redis"},
    }
    asyncio.run(registry.create_mock_dependencies(deps))

    db_mock = registry.db_mocks["db"]
    cache_mock = registry.redis_mocks["cache"]

    mocks = asyncio.run(registry.create_mock_dependencies(deps))

    assert mocks["db"] is db_mock
    assert mocks["cache"] is cache_mock


def test_create_mock_dependencies_unknown_type_skips():
    registry = UnifiedMockRegistry()
    deps = {"misc": {"type": "unknown"}}

    mocks = asyncio.run(registry.create_mock_dependencies(deps))

    assert mocks == {}


def test_configure_hitl_responses():
    registry = UnifiedMockRegistry()
    registry.configure_hitl_response("approval", True)
    registry.configure_hitl_message_response("Approve", False)

    handler = registry.get_hitl_handler()
    assert isinstance(handler, MockHITLHandler)
    assert handler.default_responses["_type_approval"] is True
    assert handler.default_responses["Approve"] is False


def test_clear_all_resets_registry():
    registry = UnifiedMockRegistry()
    registry.configure_http_response("api", None, "{}")
    registry.clear_all()

    assert registry.http_mocks == {}
    assert registry.all_mocks == {}
