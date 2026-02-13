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


def test_http_backend_predict_sync_with_cost(monkeypatch):
    """Test HTTP backend with cost_per_call wraps result."""
    response = FakeResponse({"label": "positive"})
    monkeypatch.setattr(
        "tactus.backends.http_backend.httpx.Client",
        lambda timeout=None: FakeClient(response),
    )
    backend = HTTPModelBackend("http://example", cost_per_call=0.01)
    result = backend.predict_sync({"text": "Hello"})

    # Result should be wrapped with cost
    assert result["result"] == {"label": "positive"}
    assert result["cost"]["total_cost"] == 0.01
    assert result["cost"]["prompt_cost"] == 0.01
    assert result["cost"]["completion_cost"] == 0.0
    assert result["usage"]["total_tokens"] == 0


@pytest.mark.asyncio
async def test_http_backend_predict_with_cost(monkeypatch):
    """Test async HTTP backend with cost_per_call wraps result."""
    response = FakeResponse({"label": "negative"})
    monkeypatch.setattr(
        "tactus.backends.http_backend.httpx.AsyncClient",
        lambda timeout=None: FakeAsyncClient(response),
    )
    backend = HTTPModelBackend("http://example", cost_per_call=0.02)
    result = await backend.predict({"text": "Bad"})

    # Result should be wrapped with cost
    assert result["result"] == {"label": "negative"}
    assert result["cost"]["total_cost"] == 0.02
    assert result["usage"]["prompt_tokens"] == 0


def test_http_backend_with_headers_and_timeout(monkeypatch):
    """Test HTTP backend with custom headers and timeout."""
    response = FakeResponse({"status": "ok"})
    monkeypatch.setattr(
        "tactus.backends.http_backend.httpx.Client",
        lambda timeout=None: FakeClient(response),
    )
    backend = HTTPModelBackend(
        "http://example",
        timeout=60.0,
        headers={"Authorization": "Bearer token"},
    )
    result = backend.predict_sync({"data": "test"})
    assert result == {"status": "ok"}
