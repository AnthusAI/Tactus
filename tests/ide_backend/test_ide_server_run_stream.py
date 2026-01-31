from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from tactus.ide import server as ide_server


class FakeEvent:
    def __init__(self, event_type="agent_event", timestamp=None):
        self.event_type = event_type
        self.timestamp = timestamp or datetime.utcnow()

    def model_dump(self, mode="json"):
        return {"event_type": self.event_type, "timestamp": self.timestamp.isoformat()}


class FakeIDELogHandler:
    def __init__(self):
        self.events = ide_server.queue.Queue()
        self.events.put(FakeEvent())

    def get_events(self, timeout=0.1):
        return [FakeEvent(event_type="summary_event")]


class FakeIDELogHandlerTz(FakeIDELogHandler):
    def get_events(self, timeout=0.1):
        return [FakeEvent(event_type="summary_event", timestamp=datetime.now(timezone.utc))]


class FakeIDELogHandlerQueueTz:
    def __init__(self):
        self.events = ide_server.queue.Queue()
        self.events.put(FakeEvent(timestamp=datetime.now(timezone.utc)))

    def get_events(self, timeout=0.1):
        return [FakeEvent(event_type="summary_event")]


class ErrorLogHandler(FakeIDELogHandler):
    def get_events(self, timeout=0.1):
        raise RuntimeError("log-fail")


class QueueOnlyLogHandler:
    def __init__(self):
        self.events = ide_server.queue.Queue()
        self.events.put(FakeEvent(event_type="agent_event"))

    def get_events(self, timeout=0.1):
        return []


class FakeRuntime:
    def __init__(self, *args, **kwargs):
        pass

    async def execute(self, source, context=None, format=None):
        return {"ok": True, "source": source, "context": context, "format": format}


class FakeConfigManager:
    def load_cascade(self, _path):
        return {}


class FakeControlLoopHandler:
    def __init__(self, channels=None, storage=None):
        self.channels = channels or []
        self.storage = storage


class FakeControlLoopAdapter:
    def __init__(self, handler):
        self.handler = handler


class FakeSSEChannel:
    def __init__(self):
        self.response = None
        self._events = [{"event_type": "hitl_event"}]

    async def send(self, _request):
        return SimpleNamespace(success=True, error_message=None)

    def get_next_event(self, *args, **kwargs):
        if self._events:
            return self._events.pop(0)
        return None

    def handle_ide_response(self, request_id, value):
        self.response = (request_id, value)


def _register_common_fakes(monkeypatch):
    monkeypatch.setattr("tactus.adapters.ide_log.IDELogHandler", FakeIDELogHandler)
    monkeypatch.setattr("tactus.core.runtime.TactusRuntime", FakeRuntime)
    monkeypatch.setattr("tactus.core.config_manager.ConfigManager", FakeConfigManager)
    monkeypatch.setattr("tactus.adapters.control_loop.ControlLoopHandler", FakeControlLoopHandler)
    monkeypatch.setattr(
        "tactus.adapters.control_loop.ControlLoopHITLAdapter", FakeControlLoopAdapter
    )
    monkeypatch.setattr("tactus.adapters.channels.load_default_channels", lambda **_kwargs: [])
    monkeypatch.setattr("tactus.adapters.channels.sse.SSEControlChannel", FakeSSEChannel)
    monkeypatch.setattr("nanoid.generate", lambda size=21: "run-1")


def test_run_stream_direct_execution(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    file_path = workspace / "demo.tac"
    file_path.write_text('Procedure "demo" {}')

    _register_common_fakes(monkeypatch)
    monkeypatch.setattr("tactus.sandbox.is_docker_available", lambda: (False, "no docker"))
    monkeypatch.setattr(
        "tactus.sandbox.SandboxConfig",
        lambda **_kwargs: SimpleNamespace(is_explicitly_disabled=lambda: False),
    )

    app = ide_server.create_app(initial_workspace=str(workspace))
    client = app.test_client()

    response = client.get("/api/run/stream", query_string={"path": "demo.tac"})
    data = response.data.decode("utf-8")

    assert '"lifecycle_stage": "start"' in data
    assert '"lifecycle_stage": "complete"' in data
    assert '"event_type": "summary_event"' in data
    assert "Z" in data


def test_run_stream_direct_execution_timezone_timestamp(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    file_path = workspace / "demo.tac"
    file_path.write_text('Procedure "demo" {}')

    _register_common_fakes(monkeypatch)
    monkeypatch.setattr("tactus.adapters.ide_log.IDELogHandler", FakeIDELogHandlerTz)
    monkeypatch.setattr("tactus.sandbox.is_docker_available", lambda: (False, "no docker"))
    monkeypatch.setattr(
        "tactus.sandbox.SandboxConfig",
        lambda **_kwargs: SimpleNamespace(is_explicitly_disabled=lambda: False),
    )

    app = ide_server.create_app(initial_workspace=str(workspace))
    client = app.test_client()

    response = client.get("/api/run/stream", query_string={"path": "demo.tac"})
    data = response.data.decode("utf-8")

    assert '"event_type": "summary_event"' in data


def test_run_stream_direct_execution_queue_timezone_timestamp(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    file_path = workspace / "demo.tac"
    file_path.write_text('Procedure "demo" {}')

    _register_common_fakes(monkeypatch)
    monkeypatch.setattr("tactus.adapters.ide_log.IDELogHandler", FakeIDELogHandlerQueueTz)
    monkeypatch.setattr("tactus.sandbox.is_docker_available", lambda: (False, "no docker"))
    monkeypatch.setattr(
        "tactus.sandbox.SandboxConfig",
        lambda **_kwargs: SimpleNamespace(is_explicitly_disabled=lambda: False),
    )

    app = ide_server.create_app(initial_workspace=str(workspace))
    client = app.test_client()

    response = client.get("/api/run/stream", query_string={"path": "demo.tac"})
    data = response.data.decode("utf-8")

    assert '"event_type": "summary_event"' in data
    assert "+00:00" in data


def test_run_stream_direct_execution_queue_events(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    file_path = workspace / "demo.tac"
    file_path.write_text('Procedure "demo" {}')

    _register_common_fakes(monkeypatch)
    monkeypatch.setattr("tactus.adapters.ide_log.IDELogHandler", QueueOnlyLogHandler)
    monkeypatch.setattr("tactus.sandbox.is_docker_available", lambda: (False, "no docker"))
    monkeypatch.setattr(
        "tactus.sandbox.SandboxConfig",
        lambda **_kwargs: SimpleNamespace(is_explicitly_disabled=lambda: False),
    )

    app = ide_server.create_app(initial_workspace=str(workspace))
    client = app.test_client()

    response = client.get("/api/run/stream", query_string={"path": "demo.tac"})
    data = response.data.decode("utf-8")

    assert '"event_type": "agent_event"' in data


def test_run_stream_sandbox_success(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    file_path = workspace / "demo.tac"
    file_path.write_text('Procedure "demo" {}')

    _register_common_fakes(monkeypatch)
    monkeypatch.setattr("tactus.sandbox.is_docker_available", lambda: (True, "ok"))
    monkeypatch.setattr(
        "tactus.sandbox.SandboxConfig",
        lambda **_kwargs: SimpleNamespace(is_explicitly_disabled=lambda: False),
    )

    class FakeExecResult:
        def __init__(self):
            self.status = SimpleNamespace(value="success")
            self.result = {"ok": True}
            self.error = None

    class FakeRunner:
        def __init__(self, _config):
            pass

        async def run(self, **_kwargs):
            return FakeExecResult()

    monkeypatch.setattr("tactus.sandbox.ContainerRunner", FakeRunner)

    app = ide_server.create_app(initial_workspace=str(workspace))
    client = app.test_client()

    response = client.get("/api/run/stream", query_string={"path": "demo.tac"})
    data = response.data.decode("utf-8")

    assert '"event_type": "container_status"' in data


def test_run_stream_post_writes_content(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    _register_common_fakes(monkeypatch)
    monkeypatch.setattr("tactus.sandbox.is_docker_available", lambda: (False, "no docker"))
    monkeypatch.setattr(
        "tactus.sandbox.SandboxConfig",
        lambda **_kwargs: SimpleNamespace(is_explicitly_disabled=lambda: False),
    )

    app = ide_server.create_app(initial_workspace=str(workspace))
    client = app.test_client()

    response = client.post(
        "/api/run/stream",
        json={"path": "demo.tac", "content": 'Procedure "demo" {}', "inputs": {"x": 1}},
    )
    data = response.data.decode("utf-8")

    assert '"lifecycle_stage": "complete"' in data
    assert (workspace / "demo.tac").read_text() == 'Procedure "demo" {}'


@pytest.mark.parametrize("docker_available", [True])
def test_run_stream_sandbox_execution(monkeypatch, tmp_path, docker_available):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    file_path = workspace / "demo.tac"
    file_path.write_text('Procedure "demo" {}')

    _register_common_fakes(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "key")

    class FakeStatus:
        value = "success"

    class FakeResult:
        status = FakeStatus()
        result = {"ok": True}
        error = None

    class FakeRunner:
        def __init__(self, _config):
            self.config = _config

        async def run(self, **kwargs):
            event_handler = kwargs.get("event_handler")
            if event_handler:
                event_handler({"event_type": "sandbox_event"})
            control_handler = kwargs.get("control_handler")
            if control_handler:
                await control_handler(
                    {
                        "request_id": "req-1",
                        "procedure_id": "demo",
                        "timeout_seconds": 0.01,
                        "default_value": {"ok": True},
                    }
                )
            return FakeResult()

    monkeypatch.setattr("tactus.sandbox.is_docker_available", lambda: (docker_available, "ok"))
    monkeypatch.setattr(
        "tactus.sandbox.SandboxConfig",
        lambda **_kwargs: SimpleNamespace(is_explicitly_disabled=lambda: False),
    )
    monkeypatch.setattr("tactus.sandbox.ContainerRunner", FakeRunner)
    monkeypatch.setattr(
        "tactus.protocols.control.ControlRequest.model_validate",
        lambda data: SimpleNamespace(
            request_id=data["request_id"],
            procedure_id=data["procedure_id"],
            timeout_seconds=data.get("timeout_seconds"),
            default_value=data.get("default_value"),
        ),
    )

    app = ide_server.create_app(initial_workspace=str(workspace))
    client = app.test_client()

    response = client.get("/api/run/stream", query_string={"path": "demo.tac"})
    data = response.data.decode("utf-8")

    assert '"event_type": "container_status"' in data
    assert '"event_type": "sandbox_event"' in data
    assert '"lifecycle_stage": "complete"' in data


def test_run_stream_sandbox_event_queue_drain(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    file_path = workspace / "demo.tac"
    file_path.write_text('Procedure "demo" {}')

    _register_common_fakes(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "key")

    class FakeQueue:
        def __init__(self):
            self._items = []

        def put(self, item):
            self._items.append(item)

        def get(self, timeout=None):
            if timeout == 0.01:
                raise ide_server.queue.Empty()
            if self._items:
                return self._items.pop(0)
            raise ide_server.queue.Empty()

    class FakeStatus:
        value = "success"

    class FakeResult:
        status = FakeStatus()
        result = {"ok": True}
        error = None

    captured = {}

    class FakeRunner:
        def __init__(self, _config):
            self.config = _config

        async def run(self, **kwargs):
            captured["llm_backend_config"] = kwargs.get("llm_backend_config")
            event_handler = kwargs.get("event_handler")
            if event_handler:
                event_handler({"event_type": "late_event"})
            return FakeResult()

    monkeypatch.setattr(ide_server.queue, "Queue", FakeQueue)
    monkeypatch.setattr("tactus.sandbox.is_docker_available", lambda: (True, "ok"))
    monkeypatch.setattr(
        "tactus.sandbox.SandboxConfig",
        lambda **_kwargs: SimpleNamespace(is_explicitly_disabled=lambda: False),
    )
    monkeypatch.setattr("tactus.sandbox.ContainerRunner", FakeRunner)
    monkeypatch.setattr("tactus.sandbox.container_runner.ContainerRunner", FakeRunner)

    app = ide_server.create_app(initial_workspace=str(workspace))
    client = app.test_client()

    response = client.get("/api/run/stream", query_string={"path": "demo.tac"})
    data = response.data.decode("utf-8")

    assert '"event_type": "late_event"' in data
    assert captured["llm_backend_config"]["openai_api_key"] == "key"


def test_run_stream_sandbox_no_openai_key(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    file_path = workspace / "demo.tac"
    file_path.write_text('Procedure "demo" {}')

    _register_common_fakes(monkeypatch)

    class FakeStatus:
        value = "success"

    class FakeResult:
        status = FakeStatus()
        result = {"ok": True}
        error = None

    captured = {}

    class FakeRunner:
        def __init__(self, _config):
            self.config = _config

        async def run(self, **kwargs):
            captured["llm_backend_config"] = kwargs.get("llm_backend_config")
            return FakeResult()

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr("tactus.sandbox.is_docker_available", lambda: (True, "ok"))
    monkeypatch.setattr(
        "tactus.sandbox.SandboxConfig",
        lambda **_kwargs: SimpleNamespace(is_explicitly_disabled=lambda: False),
    )
    monkeypatch.setattr("tactus.sandbox.ContainerRunner", FakeRunner)
    monkeypatch.setattr("tactus.sandbox.container_runner.ContainerRunner", FakeRunner)

    app = ide_server.create_app(initial_workspace=str(workspace))
    client = app.test_client()

    response = client.get("/api/run/stream", query_string={"path": "demo.tac"})
    data = response.data.decode("utf-8")

    assert '"lifecycle_stage": "complete"' in data
    assert captured["llm_backend_config"] == {}


def test_run_stream_container_hitl_success(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    file_path = workspace / "demo.tac"
    file_path.write_text('Procedure "demo" {}')

    _register_common_fakes(monkeypatch)

    class FakeStatus:
        value = "success"

    class FakeResult:
        status = FakeStatus()
        result = {"ok": True}
        error = None

    class FakeRunner:
        def __init__(self, _config):
            self.config = _config

        async def run(self, **kwargs):
            control_handler = kwargs.get("control_handler")
            if control_handler:
                await control_handler(
                    {
                        "request_id": "req-2",
                        "procedure_id": "demo",
                        "timeout_seconds": 1,
                        "default_value": {"ok": True},
                    }
                )
            return FakeResult()

    async def fake_to_thread(*_args, **_kwargs):
        return True

    monkeypatch.setattr("tactus.sandbox.is_docker_available", lambda: (True, "ok"))
    monkeypatch.setattr(
        "tactus.sandbox.SandboxConfig",
        lambda **_kwargs: SimpleNamespace(is_explicitly_disabled=lambda: False),
    )
    monkeypatch.setattr("tactus.sandbox.ContainerRunner", FakeRunner)
    monkeypatch.setattr(
        "tactus.protocols.control.ControlRequest.model_validate",
        lambda data: SimpleNamespace(**data),
    )
    monkeypatch.setattr("asyncio.to_thread", fake_to_thread)

    app = ide_server.create_app(initial_workspace=str(workspace))
    client = app.test_client()

    response = client.get("/api/run/stream", query_string={"path": "demo.tac"})
    data = response.data.decode("utf-8")

    assert '"lifecycle_stage": "complete"' in data


def test_run_stream_sandbox_openai_key(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    file_path = workspace / "demo.tac"
    file_path.write_text('Procedure "demo" {}')

    _register_common_fakes(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "key")
    captured = {}

    class FakeStatus:
        value = "success"

    class FakeResult:
        status = FakeStatus()
        result = {"ok": True}
        error = None

    class FakeRunner:
        def __init__(self, _config):
            self.config = _config

        async def run(self, **kwargs):
            captured["called"] = True
            captured["llm_backend_config"] = kwargs.get("llm_backend_config")
            return FakeResult()

    monkeypatch.setattr("tactus.sandbox.is_docker_available", lambda: (True, "ok"))
    monkeypatch.setattr(
        "tactus.sandbox.SandboxConfig",
        lambda **_kwargs: SimpleNamespace(is_explicitly_disabled=lambda: False),
    )
    monkeypatch.setattr("tactus.sandbox.ContainerRunner", FakeRunner)
    monkeypatch.setattr(
        "tactus.core.config_manager.ConfigManager",
        lambda: SimpleNamespace(load_cascade=lambda _path: {"openai": {"api_key": "key"}}),
    )
    monkeypatch.setattr(
        ide_server.os.environ,
        "get",
        lambda key, default=None: "key" if key == "OPENAI_API_KEY" else default,
    )

    app = ide_server.create_app(initial_workspace=str(workspace))
    client = app.test_client()

    response = client.get("/api/run/stream", query_string={"path": "demo.tac"})
    data = response.data.decode("utf-8")

    assert '"event_type": "container_status"' in data
    assert captured["called"] is True
    assert captured["llm_backend_config"]["openai_api_key"] == "key"


def test_run_stream_streaming_error_event(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    file_path = workspace / "demo.tac"
    file_path.write_text('Procedure "demo" {}')

    _register_common_fakes(monkeypatch)
    monkeypatch.setattr("tactus.adapters.ide_log.IDELogHandler", ErrorLogHandler)
    monkeypatch.setattr("tactus.sandbox.is_docker_available", lambda: (False, "no docker"))
    monkeypatch.setattr(
        "tactus.sandbox.SandboxConfig",
        lambda **_kwargs: SimpleNamespace(is_explicitly_disabled=lambda: False),
    )

    app = ide_server.create_app(initial_workspace=str(workspace))
    client = app.test_client()

    response = client.get("/api/run/stream", query_string={"path": "demo.tac"})
    data = response.data.decode("utf-8")

    assert '"lifecycle_stage": "error"' in data


def test_run_stream_setup_value_error(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    _register_common_fakes(monkeypatch)
    monkeypatch.setattr("tactus.sandbox.is_docker_available", lambda: (False, "no docker"))
    monkeypatch.setattr(
        "tactus.sandbox.SandboxConfig",
        lambda **_kwargs: SimpleNamespace(is_explicitly_disabled=lambda: False),
    )
    monkeypatch.setattr(
        ide_server,
        "_resolve_workspace_path",
        lambda _path: (_ for _ in ()).throw(ValueError("bad")),
    )

    app = ide_server.create_app(initial_workspace=str(workspace))
    client = app.test_client()

    response = client.get("/api/run/stream", query_string={"path": "demo.tac"})
    assert response.status_code == 400


def test_run_stream_setup_unexpected_error(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    file_path = workspace / "demo.tac"
    file_path.write_text("content")

    _register_common_fakes(monkeypatch)
    monkeypatch.setattr("tactus.sandbox.is_docker_available", lambda: (False, "no docker"))
    monkeypatch.setattr(
        "tactus.sandbox.SandboxConfig",
        lambda **_kwargs: SimpleNamespace(is_explicitly_disabled=lambda: False),
    )
    monkeypatch.setattr(
        ide_server,
        "_resolve_workspace_path",
        lambda _path: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    app = ide_server.create_app(initial_workspace=str(workspace))
    client = app.test_client()

    response = client.get("/api/run/stream", query_string={"path": "demo.tac"})
    assert response.status_code == 500


def test_run_stream_container_hitl_delivery_failure(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    file_path = workspace / "demo.tac"
    file_path.write_text('Procedure "demo" {}')

    class FailingChannel(FakeSSEChannel):
        async def send(self, _request):
            return SimpleNamespace(success=False, error_message="boom")

    _register_common_fakes(monkeypatch)
    monkeypatch.setattr("tactus.adapters.channels.sse.SSEControlChannel", FailingChannel)

    class FakeStatus:
        value = "success"

    class FakeResult:
        status = FakeStatus()
        result = {"ok": True}
        error = None

    class FakeRunner:
        def __init__(self, _config):
            self.config = _config

        async def run(self, **kwargs):
            control_handler = kwargs.get("control_handler")
            if control_handler:
                await control_handler(
                    {
                        "request_id": "req-3",
                        "procedure_id": "demo",
                        "timeout_seconds": 1,
                        "default_value": {"ok": True},
                    }
                )
            return FakeResult()

    monkeypatch.setattr("tactus.sandbox.is_docker_available", lambda: (True, "ok"))
    monkeypatch.setattr(
        "tactus.sandbox.SandboxConfig",
        lambda **_kwargs: SimpleNamespace(is_explicitly_disabled=lambda: False),
    )
    monkeypatch.setattr("tactus.sandbox.ContainerRunner", FakeRunner)
    monkeypatch.setattr(
        "tactus.protocols.control.ControlRequest.model_validate",
        lambda data: SimpleNamespace(**data),
    )

    app = ide_server.create_app(initial_workspace=str(workspace))
    client = app.test_client()

    response = client.get("/api/run/stream", query_string={"path": "demo.tac"})
    data = response.data.decode("utf-8")

    assert '"lifecycle_stage": "error"' in data


def test_run_stream_sandbox_failure(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    file_path = workspace / "demo.tac"
    file_path.write_text('Procedure "demo" {}')

    _register_common_fakes(monkeypatch)

    class FakeStatus:
        value = "error"

    class FakeResult:
        status = FakeStatus()
        result = None
        error = "boom"

    class FakeRunner:
        def __init__(self, _config):
            self.config = _config

        async def run(self, **_kwargs):
            return FakeResult()

    monkeypatch.setattr("tactus.sandbox.is_docker_available", lambda: (True, "ok"))
    monkeypatch.setattr(
        "tactus.sandbox.SandboxConfig",
        lambda **_kwargs: SimpleNamespace(is_explicitly_disabled=lambda: False),
    )
    monkeypatch.setattr("tactus.sandbox.ContainerRunner", FakeRunner)

    app = ide_server.create_app(initial_workspace=str(workspace))
    client = app.test_client()

    response = client.get("/api/run/stream", query_string={"path": "demo.tac"})
    data = response.data.decode("utf-8")

    assert '"lifecycle_stage": "error"' in data


def test_run_stream_direct_execution_error(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    file_path = workspace / "demo.tac"
    file_path.write_text('Procedure "demo" {}')

    class ErrorRuntime(FakeRuntime):
        async def execute(self, *_args, **_kwargs):
            raise RuntimeError("boom")

    _register_common_fakes(monkeypatch)
    monkeypatch.setattr("tactus.core.runtime.TactusRuntime", ErrorRuntime)
    monkeypatch.setattr("tactus.sandbox.is_docker_available", lambda: (False, "no docker"))
    monkeypatch.setattr(
        "tactus.sandbox.SandboxConfig",
        lambda **_kwargs: SimpleNamespace(is_explicitly_disabled=lambda: False),
    )

    app = ide_server.create_app(initial_workspace=str(workspace))
    client = app.test_client()

    response = client.get("/api/run/stream", query_string={"path": "demo.tac"})
    data = response.data.decode("utf-8")

    assert '"lifecycle_stage": "error"' in data


def test_run_stream_event_serialization_errors(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    file_path = workspace / "demo.tac"
    file_path.write_text('Procedure "demo" {}')

    class BadEvent:
        def __init__(self):
            self.timestamp = datetime.utcnow()

        def model_dump(self, mode="json"):
            raise RuntimeError("boom")

    class BadLogHandler:
        def __init__(self):
            self.events = ide_server.queue.Queue()
            self.events.put(BadEvent())

        def get_events(self, timeout=0.1):
            return [BadEvent()]

    _register_common_fakes(monkeypatch)
    monkeypatch.setattr("tactus.adapters.ide_log.IDELogHandler", BadLogHandler)
    monkeypatch.setattr("tactus.sandbox.is_docker_available", lambda: (False, "no docker"))
    monkeypatch.setattr(
        "tactus.sandbox.SandboxConfig",
        lambda **_kwargs: SimpleNamespace(is_explicitly_disabled=lambda: False),
    )

    app = ide_server.create_app(initial_workspace=str(workspace))
    client = app.test_client()

    response = client.get("/api/run/stream", query_string={"path": "demo.tac"})
    data = response.data.decode("utf-8")

    assert '"lifecycle_stage": "complete"' in data


def test_run_stream_consolidates_stream_chunks(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    file_path = workspace / "demo.tac"
    file_path.write_text('Procedure "demo" {}')

    class ChunkEvent(FakeEvent):
        def model_dump(self, mode="json"):
            return {
                "event_type": "agent_stream_chunk",
                "agent_name": "agent",
                "timestamp": self.timestamp.isoformat(),
                "content": "chunk",
            }

    class ChunkLogHandler(FakeIDELogHandler):
        def __init__(self):
            self.events = ide_server.queue.Queue()
            self.events.put(ChunkEvent())

        def get_events(self, timeout=0.1):
            return [ChunkEvent()]

    _register_common_fakes(monkeypatch)
    monkeypatch.setattr("tactus.adapters.ide_log.IDELogHandler", ChunkLogHandler)
    monkeypatch.setattr("tactus.sandbox.is_docker_available", lambda: (False, "no docker"))
    monkeypatch.setattr(
        "tactus.sandbox.SandboxConfig",
        lambda **_kwargs: SimpleNamespace(is_explicitly_disabled=lambda: False),
    )

    app = ide_server.create_app(initial_workspace=str(workspace))
    client = app.test_client()

    response = client.get("/api/run/stream", query_string={"path": "demo.tac"})
    data = response.data.decode("utf-8")

    assert '"agent_stream_chunk"' in data


def test_run_stream_save_events_error(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    file_path = workspace / "demo.tac"
    file_path.write_text('Procedure "demo" {}')

    _register_common_fakes(monkeypatch)
    monkeypatch.setattr("tactus.sandbox.is_docker_available", lambda: (False, "no docker"))
    monkeypatch.setattr(
        "tactus.sandbox.SandboxConfig",
        lambda **_kwargs: SimpleNamespace(is_explicitly_disabled=lambda: False),
    )

    real_open = open

    def failing_open(path, mode="r", *args, **kwargs):
        if "w" in mode and str(path).endswith(".json"):
            raise RuntimeError("boom")
        return real_open(path, mode, *args, **kwargs)

    monkeypatch.setattr("builtins.open", failing_open)

    app = ide_server.create_app(initial_workspace=str(workspace))
    client = app.test_client()

    response = client.get("/api/run/stream", query_string={"path": "demo.tac"})
    data = response.data.decode("utf-8")

    assert '"lifecycle_stage": "complete"' in data
