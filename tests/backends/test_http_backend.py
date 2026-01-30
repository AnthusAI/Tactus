import pytest

from tactus.backends.http_backend import HTTPModelBackend


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class FakeClient:
    def __init__(self, response):
        self._response = response

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, endpoint, json=None, headers=None):
        return self._response


class FakeAsyncClient:
    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, endpoint, json=None, headers=None):
        return self._response


@pytest.mark.asyncio
async def test_http_backend_predict(monkeypatch):
    response = FakeResponse({"ok": True})
    monkeypatch.setattr(
        "tactus.backends.http_backend.httpx.AsyncClient",
        lambda timeout=None: FakeAsyncClient(response),
    )
    backend = HTTPModelBackend("http://example")
    result = await backend.predict({"x": 1})
    assert result == {"ok": True}


def test_http_backend_predict_sync(monkeypatch):
    response = FakeResponse({"ok": True})
    monkeypatch.setattr(
        "tactus.backends.http_backend.httpx.Client",
        lambda timeout=None: FakeClient(response),
    )
    backend = HTTPModelBackend("http://example")
    result = backend.predict_sync({"x": 1})
    assert result == {"ok": True}
