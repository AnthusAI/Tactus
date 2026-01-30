import pytest

from tactus.testing import mock_dependencies


def test_mock_response_json_and_headers_default():
    response = mock_dependencies.MockResponse(text='{"a": 1}')
    assert response.headers == {}
    assert response.json() == {"a": 1}


def test_mock_response_preserves_headers():
    response = mock_dependencies.MockResponse(text="{}", headers={"x": "y"})
    assert response.headers == {"x": "y"}


@pytest.mark.asyncio
async def test_mock_http_client_get_and_post_tracking():
    client = mock_dependencies.MockHTTPClient({"/ok": '{"status": "ok"}'})
    client.add_response("/created", '{"id": 1}', status_code=201)
    client.add_response("/dict-get", '{"ready": true}', status_code=202)

    get_response = await client.get("/ok", params={"q": "x"})
    dict_get_response = await client.get("/dict-get")
    post_response = await client.post("/created", json={"name": "t"})
    string_post_response = await client.post("/ok")
    default_response = await client.get("/missing")

    assert get_response.status_code == 200
    assert dict_get_response.status_code == 202
    assert post_response.status_code == 201
    assert string_post_response.status_code == 200
    assert default_response.text == "{}"
    assert client.was_called("GET", "/ok") is True
    assert client.was_called("POST", "/created") is True
    assert client.was_called(method="POST", path="/missing") is False
    assert client.was_called(method="PUT") is False

    await client.aclose()


@pytest.mark.asyncio
async def test_mock_redis_set_get_delete():
    redis = mock_dependencies.MockRedis()
    await redis.set("key", "value")
    assert await redis.get("key") == "value"
    await redis.delete("key")
    assert await redis.get("key") is None
    await redis.delete("missing")
    await redis.close()


@pytest.mark.asyncio
async def test_mock_dependency_factory_create_all():
    dependencies_config = {
        "api": {"type": "http_client", "base_url": "https://example.com"},
        "db": {"type": "postgres"},
        "cache": {"type": "redis"},
    }
    mocks = await mock_dependencies.MockDependencyFactory.create_all_mocks(
        dependencies_config, mock_responses={"api": {"/ok": "{}"}}
    )

    assert mocks["api"].base_url == "https://example.com"
    assert isinstance(mocks["db"], mock_dependencies.MockDatabase)
    assert isinstance(mocks["cache"], mock_dependencies.MockRedis)
    await mocks["db"].close()


@pytest.mark.asyncio
async def test_mock_dependency_factory_unknown_type_raises():
    with pytest.raises(ValueError):
        await mock_dependencies.MockDependencyFactory.create_mock("unknown", {}, None)


@pytest.mark.asyncio
async def test_mock_http_client_get_calls():
    client = mock_dependencies.MockHTTPClient()
    await client.get("/path")

    assert client.get_calls() == [("GET", "/path", {})]
