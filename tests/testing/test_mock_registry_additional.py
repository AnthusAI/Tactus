import pytest

from tactus.testing.mock_registry import UnifiedMockRegistry


@pytest.mark.asyncio
async def test_create_mock_dependencies_reuses_http_mock():
    registry = UnifiedMockRegistry()
    registry.configure_http_response("api", "/ping", '{"ok": true}', status_code=200)

    mocks = await registry.create_mock_dependencies({"api": {"type": "http_client"}})

    assert mocks["api"] is registry.http_mocks["api"]
    assert registry.get_mock("api") is mocks["api"]


@pytest.mark.asyncio
async def test_create_mock_dependencies_skips_unknown_type():
    registry = UnifiedMockRegistry()
    mocks = await registry.create_mock_dependencies({"bad": {"type": "unknown"}})
    assert mocks == {}


def test_configure_http_response_default_path():
    registry = UnifiedMockRegistry()
    registry.configure_http_response("api", None, '{"ok": true}', status_code=201)

    default = registry.http_mocks["api"].responses["_default"]
    assert default == {"text": '{"ok": true}', "status_code": 201}


def test_clear_all_resets_state():
    registry = UnifiedMockRegistry()
    registry.configure_http_response("api", "/ping", '{"ok": true}')
    registry.clear_all()

    assert registry.http_mocks == {}
    assert registry.all_mocks == {}
