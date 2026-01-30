import asyncio
import json

import pytest

from tactus.broker.stdio import STDIO_REQUEST_PREFIX
from tactus.sandbox.config import SandboxConfig
from tactus.sandbox.container_runner import ContainerRunner
from tactus.sandbox.protocol import (
    ExecutionRequest,
    ExecutionResult,
    ExecutionStatus,
    RESULT_END_MARKER,
    RESULT_START_MARKER,
)


class DummyStream:
    def __init__(self, lines):
        self._lines = list(lines)

    async def readline(self):
        if not self._lines:
            await asyncio.sleep(0)
            return b""
        return self._lines.pop(0)


class DummyStdin:
    def __init__(self):
        self.buffer = bytearray()
        self._closed = False

    def write(self, data: bytes) -> None:
        self.buffer.extend(data)

    async def drain(self):
        return None

    def close(self) -> None:
        self._closed = True

    def is_closing(self) -> bool:
        return self._closed


class FlakyStdin(DummyStdin):
    def __init__(self, fail_on_write=False):
        super().__init__()
        self._fail_on_write = fail_on_write
        self._writes = 0

    def write(self, data: bytes) -> None:
        self._writes += 1
        if self._fail_on_write and self._writes > 1:
            raise BrokenPipeError("boom")
        super().write(data)

    async def drain(self):
        if self._fail_on_write and self._writes > 1:
            raise ConnectionResetError("boom")
        return None


class DummyProcess:
    def __init__(self, stdout_lines, stderr_lines, returncode=0):
        self.pid = 123
        self.stdin = DummyStdin()
        self.stdout = DummyStream(stdout_lines)
        self.stderr = DummyStream(stderr_lines)
        self.returncode = returncode

    async def wait(self):
        return self.returncode

    def kill(self):
        self.returncode = 137


class FakeToolRegistry:
    def __init__(self, behavior):
        self.behavior = behavior

    def call(self, name, args):
        if name in self.behavior:
            outcome = self.behavior[name]
            if isinstance(outcome, Exception):
                raise outcome
            return outcome
        raise KeyError(name)


class FakeChatResponse:
    def __init__(self, content):
        class Message:
            def __init__(self, text):
                self.content = text

        class Choice:
            def __init__(self, text):
                self.message = Message(text)

        self.choices = [Choice(content)]


class FakeDelta:
    def __init__(self, content):
        self.content = content


class FakeChunk:
    def __init__(self, content):
        class Choice:
            def __init__(self, text):
                self.delta = FakeDelta(text)

        self.choices = [Choice(content)]


class FakeBadChunk:
    choices = []


class FakeChatBackend:
    async def chat(self, model, messages, temperature=None, max_tokens=None, stream=False):
        if model == "boom":
            raise RuntimeError("boom")
        if model == "no-choices":

            class Empty:
                choices = []

            return Empty()
        if stream:

            async def _gen():
                if model == "stream-bad":
                    yield FakeBadChunk()
                for text in ["part1", "part2"]:
                    yield FakeChunk(text)

            return _gen()
        return FakeChatResponse("hello")


class BrokenCloseStdin(DummyStdin):
    def close(self) -> None:
        raise RuntimeError("boom")


class ClosedStdin(DummyStdin):
    def __init__(self):
        super().__init__()
        self._closed = True


class ExplodingStream(DummyStream):
    async def readline(self):
        raise ValueError("boom")


@pytest.mark.asyncio
async def test_run_container_returns_structured_result(monkeypatch):
    config = SandboxConfig(mount_current_dir=False, broker_transport="tcp")
    runner = ContainerRunner(config)

    result_payload = ExecutionResult.success(result={"ok": True}).to_json()
    stdout_lines = [
        f"{RESULT_START_MARKER}\n".encode("utf-8"),
        f"{result_payload}\n".encode("utf-8"),
        f"{RESULT_END_MARKER}\n".encode("utf-8"),
    ]
    process = DummyProcess(stdout_lines, [], returncode=0)

    async def fake_create_subprocess_exec(*_args, **_kwargs):
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    request = ExecutionRequest(source="return {}", working_dir="/workspace")
    result = await runner._run_container(["docker"], request, timeout=1)

    assert result.status == ExecutionStatus.SUCCESS
    assert result.result == {"ok": True}


@pytest.mark.asyncio
async def test_run_container_handles_no_result_and_oom(monkeypatch):
    config = SandboxConfig(mount_current_dir=False, broker_transport="tcp")
    runner = ContainerRunner(config)

    process = DummyProcess([b""], [b""], returncode=137)

    async def fake_create_subprocess_exec(*_args, **_kwargs):
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    request = ExecutionRequest(source="return {}", working_dir="/workspace")
    result = await runner._run_container(["docker"], request, timeout=1)

    assert result.status == ExecutionStatus.ERROR
    assert result.error_type == "OutOfMemoryError"
    assert result.exit_code == 137


@pytest.mark.asyncio
async def test_run_container_falls_back_to_stdout(monkeypatch):
    config = SandboxConfig(mount_current_dir=False, broker_transport="tcp")
    runner = ContainerRunner(config)

    process = DummyProcess([b"plain output\n", b""], [b""], returncode=0)

    async def fake_create_subprocess_exec(*_args, **_kwargs):
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    request = ExecutionRequest(source="return {}", working_dir="/workspace")
    result = await runner._run_container(["docker"], request, timeout=1)

    assert result.status == ExecutionStatus.SUCCESS
    assert result.result == "plain output"


@pytest.mark.asyncio
async def test_run_container_wait_for_tasks_timeout(monkeypatch):
    config = SandboxConfig(mount_current_dir=False, broker_transport="tcp")
    runner = ContainerRunner(config)

    process = DummyProcess([b""], [b""], returncode=0)

    async def fake_create_subprocess_exec(*_args, **_kwargs):
        return process

    original_create_task = asyncio.create_task

    async def boom_stdout():
        raise ValueError("stdout boom")

    async def boom_stderr():
        raise RuntimeError("stderr boom")

    def fake_create_task(coro, *args, **kwargs):
        name = coro.cr_code.co_name
        if name == "stdout_loop":
            coro.close()
            return original_create_task(boom_stdout())
        if name == "stderr_loop":
            coro.close()
            return original_create_task(boom_stderr())
        return original_create_task(coro, *args, **kwargs)

    async def fake_wait_for(_task, _timeout=None, **_kwargs):
        raise asyncio.TimeoutError

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create_subprocess_exec)
    monkeypatch.setattr(asyncio, "create_task", fake_create_task)
    monkeypatch.setattr(asyncio, "wait_for", fake_wait_for)

    request = ExecutionRequest(source="return {}", working_dir="/workspace")
    result = await runner._run_container(["docker"], request, timeout=1)

    assert result.status == ExecutionStatus.SUCCESS


@pytest.mark.asyncio
async def test_run_container_timeout_kills_process_tcp(monkeypatch):
    config = SandboxConfig(mount_current_dir=False, broker_transport="tcp")
    runner = ContainerRunner(config)

    class HangingProcess:
        def __init__(self):
            self.pid = 123
            self.stdin = BrokenCloseStdin()
            self.stdout = ExplodingStream([])
            self.stderr = DummyStream([b""])
            self.returncode = None
            self._killed = False

        async def wait(self):
            while not self._killed:
                await asyncio.sleep(0)
            self.returncode = 137
            return self.returncode

        def kill(self):
            self._killed = True
            raise RuntimeError("kill failed")

    process = HangingProcess()

    async def fake_create_subprocess_exec(*_args, **_kwargs):
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    request = ExecutionRequest(source="return {}", working_dir="/workspace")
    with pytest.raises(asyncio.TimeoutError):
        await runner._run_container(["docker"], request, timeout=0)


@pytest.mark.asyncio
async def test_run_container_handles_stdio_broker_requests(monkeypatch):
    config = SandboxConfig(mount_current_dir=False, broker_transport="stdio")
    runner = ContainerRunner(config)

    monkeypatch.setattr(
        "tactus.broker.server.HostToolRegistry.default", lambda: FakeToolRegistry({})
    )
    monkeypatch.setattr(
        "tactus.broker.server.OpenAIChatBackend", lambda api_key=None: FakeChatBackend()
    )

    result_payload = ExecutionResult.success(result={"ok": True}).to_json()
    stdout_lines = [
        f"{RESULT_START_MARKER}\n".encode("utf-8"),
        f"{result_payload}\n".encode("utf-8"),
        f"{RESULT_END_MARKER}\n".encode("utf-8"),
        b"",
    ]

    broker_requests = [
        {"id": 123, "method": None, "params": {}},
        {"id": "evt", "method": "events.emit", "params": {"event": {"type": "ping"}}},
        {"id": "control", "method": "control.request", "params": {"request": {"x": 1}}},
        {"id": "tool", "method": "tool.call", "params": {"name": "missing"}},
        {"id": "llm", "method": "llm.chat", "params": {"model": "gpt", "messages": []}},
        {
            "id": "llm_no_choices",
            "method": "llm.chat",
            "params": {"model": "no-choices", "messages": []},
        },
        {
            "id": "llm_stream",
            "method": "llm.chat",
            "params": {"model": "stream-bad", "messages": [], "stream": True},
        },
        {"id": "unknown", "method": "unknown.method", "params": {}},
    ]
    stderr_lines = [
        f"{STDIO_REQUEST_PREFIX}{json.dumps(req)}\n".encode("utf-8") for req in broker_requests
    ] + [b""]

    process = DummyProcess(stdout_lines, stderr_lines, returncode=0)

    async def fake_create_subprocess_exec(*_args, **_kwargs):
        return process

    async def control_handler(request):
        raise asyncio.TimeoutError

    events = []

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    request = ExecutionRequest(source="return {}", working_dir="/workspace")
    result = await runner._run_container(
        ["docker"],
        request,
        timeout=1,
        event_handler=events.append,
        control_handler=control_handler,
    )

    assert result.status == ExecutionStatus.SUCCESS
    assert events == [{"type": "ping"}]

    payload_lines = [line for line in process.stdin.buffer.split(b"\n") if line.strip()]
    response_lines = [line.decode("utf-8") for line in payload_lines[1:]]
    responses = [json.loads(line) for line in response_lines]
    response_by_id = {resp.get("id"): resp for resp in responses if isinstance(resp, dict)}
    events_by_id = {}
    for resp in responses:
        if not isinstance(resp, dict):
            continue
        events_by_id.setdefault(resp.get("id"), []).append(resp)

    assert response_by_id["evt"]["event"] == "done"
    assert response_by_id["control"]["event"] == "timeout"
    assert response_by_id["tool"]["event"] == "error"
    assert response_by_id["llm"]["event"] == "done"
    assert response_by_id["unknown"]["event"] == "error"
    assert response_by_id["llm_no_choices"]["event"] == "done"
    assert any(event["event"] == "delta" for event in events_by_id["llm_stream"])
    assert any(event["event"] == "done" for event in events_by_id["llm_stream"])


@pytest.mark.asyncio
async def test_run_container_stdio_broker_error_branches(monkeypatch):
    config = SandboxConfig(mount_current_dir=False, broker_transport="stdio")
    runner = ContainerRunner(config)

    tool_registry = FakeToolRegistry(
        {
            "explode": RuntimeError("boom"),
        }
    )
    monkeypatch.setattr("tactus.broker.server.HostToolRegistry.default", lambda: tool_registry)
    monkeypatch.setattr(
        "tactus.broker.server.OpenAIChatBackend", lambda api_key=None: FakeChatBackend()
    )

    result_payload = ExecutionResult.success(result={"ok": True}).to_json()
    stdout_lines = [
        f"{RESULT_START_MARKER}\n".encode("utf-8"),
        f"{result_payload}\n".encode("utf-8"),
        f"{RESULT_END_MARKER}\n".encode("utf-8"),
        b"",
    ]

    broker_requests = [
        {"id": "bad_method", "method": 123, "params": {}},
        {"id": "control", "method": "control.request", "params": {"request": {}}},
        {"id": "tool_args", "method": "tool.call", "params": {"name": "explode", "args": "nope"}},
        {"id": "tool_name", "method": "tool.call", "params": {"name": 123, "args": {}}},
        {"id": "tool_fail", "method": "tool.call", "params": {"name": "explode", "args": {}}},
        {
            "id": "provider",
            "method": "llm.chat",
            "params": {"provider": "anthropic", "model": "x", "messages": []},
        },
        {"id": "model", "method": "llm.chat", "params": {"messages": []}},
        {"id": "messages", "method": "llm.chat", "params": {"model": "gpt", "messages": "nope"}},
        {"id": "llm_error", "method": "llm.chat", "params": {"model": "boom", "messages": []}},
    ]
    stderr_lines = [
        f"{STDIO_REQUEST_PREFIX}{json.dumps(req)}\n".encode("utf-8") for req in broker_requests
    ] + [b""]

    process = DummyProcess(stdout_lines, stderr_lines, returncode=0)

    async def fake_create_subprocess_exec(*_args, **_kwargs):
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    request = ExecutionRequest(source="return {}", working_dir="/workspace")
    result = await runner._run_container(["docker"], request, timeout=1)

    assert result.status == ExecutionStatus.SUCCESS

    payload_lines = [line for line in process.stdin.buffer.split(b"\n") if line.strip()]
    response_lines = [line.decode("utf-8") for line in payload_lines[1:]]
    responses = [json.loads(line) for line in response_lines]
    response_by_id = {resp.get("id"): resp for resp in responses if isinstance(resp, dict)}

    assert response_by_id["bad_method"]["event"] == "error"
    assert response_by_id["control"]["event"] == "error"
    assert response_by_id["tool_args"]["event"] == "error"
    assert response_by_id["tool_name"]["event"] == "error"
    assert response_by_id["tool_fail"]["event"] == "error"
    assert response_by_id["provider"]["event"] == "error"
    assert response_by_id["model"]["event"] == "error"
    assert response_by_id["messages"]["event"] == "error"
    assert response_by_id["llm_error"]["event"] == "error"


@pytest.mark.asyncio
async def test_run_container_handles_invalid_json_and_broker_noise(monkeypatch):
    config = SandboxConfig(mount_current_dir=False, broker_transport="stdio")
    runner = ContainerRunner(config)

    monkeypatch.setattr(
        "tactus.broker.server.HostToolRegistry.default", lambda: FakeToolRegistry({})
    )
    monkeypatch.setattr(
        "tactus.broker.server.OpenAIChatBackend", lambda api_key=None: FakeChatBackend()
    )

    stdout_lines = [
        f"{RESULT_START_MARKER}\n".encode("utf-8"),
        b"{bad json}\n",
        f"{RESULT_END_MARKER}\n".encode("utf-8"),
        b"",
    ]
    stderr_lines = [
        f"{STDIO_REQUEST_PREFIX}not-json\n".encode("utf-8"),
        f"{STDIO_REQUEST_PREFIX}[1, 2, 3]\n".encode("utf-8"),
        b"\n",
        b"plain stderr line\n",
        b"",
    ]

    process = DummyProcess(stdout_lines, stderr_lines, returncode=0)

    async def fake_create_subprocess_exec(*_args, **_kwargs):
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    request = ExecutionRequest(source="return {}", working_dir="/workspace")
    result = await runner._run_container(["docker"], request, timeout=1)

    assert result.status == ExecutionStatus.SUCCESS
    assert "<<<TACTUS_RESULT_START>>>" in result.result


@pytest.mark.asyncio
async def test_run_container_timeout_handles_task_errors(monkeypatch):
    config = SandboxConfig(mount_current_dir=False, broker_transport="tcp")
    runner = ContainerRunner(config)

    class HangingProcess:
        def __init__(self):
            self.pid = 123
            self.stdin = BrokenCloseStdin()
            self.stdout = DummyStream([b""])
            self.stderr = DummyStream([b""])
            self.returncode = None

        async def wait(self):
            await asyncio.sleep(0)
            return self.returncode

        def kill(self):
            raise RuntimeError("kill failed")

    process = HangingProcess()

    async def fake_create_subprocess_exec(*_args, **_kwargs):
        return process

    original_create_task = asyncio.create_task

    async def boom_stdout():
        raise ValueError("stdout boom")

    async def boom_stderr():
        raise RuntimeError("stderr boom")

    def fake_create_task(coro, *args, **kwargs):
        name = coro.cr_code.co_name
        if name == "stdout_loop":
            coro.close()
            return original_create_task(boom_stdout())
        if name == "stderr_loop":
            coro.close()
            return original_create_task(boom_stderr())
        return original_create_task(coro, *args, **kwargs)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create_subprocess_exec)
    monkeypatch.setattr(asyncio, "create_task", fake_create_task)

    request = ExecutionRequest(source="return {}", working_dir="/workspace")
    with pytest.raises(asyncio.TimeoutError):
        await runner._run_container(["docker"], request, timeout=0)


@pytest.mark.asyncio
async def test_run_container_handles_stdin_close_errors(monkeypatch):
    config = SandboxConfig(mount_current_dir=False, broker_transport="tcp")
    runner = ContainerRunner(config)

    class BrokenStdin(DummyStdin):
        def close(self) -> None:
            raise RuntimeError("nope")

    class BrokenProcess(DummyProcess):
        def __init__(self, stdout_lines, stderr_lines, returncode=0):
            super().__init__(stdout_lines, stderr_lines, returncode=returncode)
            self.stdin = BrokenStdin()

    result_payload = ExecutionResult.success(result={"ok": True}).to_json()
    stdout_lines = [
        f"{RESULT_START_MARKER}\n".encode("utf-8"),
        f"{result_payload}\n".encode("utf-8"),
        f"{RESULT_END_MARKER}\n".encode("utf-8"),
        b"",
    ]
    process = BrokenProcess(stdout_lines, [b""], returncode=0)

    async def fake_create_subprocess_exec(*_args, **_kwargs):
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    request = ExecutionRequest(source="return {}", working_dir="/workspace")
    result = await runner._run_container(["docker"], request, timeout=1)

    assert result.status == ExecutionStatus.SUCCESS


@pytest.mark.asyncio
async def test_run_container_wait_for_timeout_cancels_tasks(monkeypatch):
    config = SandboxConfig(mount_current_dir=False, broker_transport="tcp")
    runner = ContainerRunner(config)

    result_payload = ExecutionResult.success(result={"ok": True}).to_json()
    stdout_lines = [
        f"{RESULT_START_MARKER}\n".encode("utf-8"),
        f"{result_payload}\n".encode("utf-8"),
        f"{RESULT_END_MARKER}\n".encode("utf-8"),
        b"",
    ]
    process = DummyProcess(stdout_lines, [b""], returncode=0)

    async def fake_create_subprocess_exec(*_args, **_kwargs):
        return process

    async def raise_timeout(task, timeout=None):
        raise asyncio.TimeoutError

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create_subprocess_exec)
    monkeypatch.setattr(asyncio, "wait_for", raise_timeout)

    request = ExecutionRequest(source="return {}", working_dir="/workspace")
    result = await runner._run_container(["docker"], request, timeout=1)

    assert result.status == ExecutionStatus.SUCCESS


@pytest.mark.asyncio
async def test_run_container_handles_exit_code_timeout(monkeypatch):
    config = SandboxConfig(mount_current_dir=False, broker_transport="tcp")
    runner = ContainerRunner(config)

    process = DummyProcess([b""], [b""], returncode=124)

    async def fake_create_subprocess_exec(*_args, **_kwargs):
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    request = ExecutionRequest(source="return {}", working_dir="/workspace")
    result = await runner._run_container(["docker"], request, timeout=1)

    assert result.status == ExecutionStatus.ERROR
    assert result.error_type == "TimeoutError"


@pytest.mark.asyncio
async def test_run_container_timeout_kills_process(monkeypatch):
    config = SandboxConfig(mount_current_dir=False, broker_transport="tcp")
    runner = ContainerRunner(config)

    class SlowProcess(DummyProcess):
        def __init__(self):
            super().__init__([b""], [b""], returncode=0)
            self.killed = False

        async def wait(self):
            await asyncio.sleep(1)
            return 0

        def kill(self):
            self.killed = True

    process = SlowProcess()

    async def fake_create_subprocess_exec(*_args, **_kwargs):
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    request = ExecutionRequest(source="return {}", working_dir="/workspace")

    with pytest.raises(asyncio.TimeoutError):
        await runner._run_container(["docker"], request, timeout=0)

    assert process.killed is True


@pytest.mark.asyncio
async def test_run_container_broker_control_success_and_error(monkeypatch):
    config = SandboxConfig(mount_current_dir=False, broker_transport="stdio")
    runner = ContainerRunner(config)

    monkeypatch.setattr(
        "tactus.broker.server.HostToolRegistry.default",
        lambda: FakeToolRegistry({"ok": {"status": "ok"}}),
    )
    monkeypatch.setattr(
        "tactus.broker.server.OpenAIChatBackend", lambda api_key=None: FakeChatBackend()
    )

    result_payload = ExecutionResult.success(result={"ok": True}).to_json()
    stdout_lines = [
        f"{RESULT_START_MARKER}\n".encode("utf-8"),
        f"{result_payload}\n".encode("utf-8"),
        f"{RESULT_END_MARKER}\n".encode("utf-8"),
        b"",
    ]

    broker_requests = [
        {"id": "control_ok", "method": "control.request", "params": {"request": {"x": 1}}},
        {"id": "control_fail", "method": "control.request", "params": {"request": {"x": 2}}},
        {"id": "tool_ok", "method": "tool.call", "params": {"name": "ok", "args": {}}},
    ]
    stderr_lines = [
        f"{STDIO_REQUEST_PREFIX}{json.dumps(req)}\n".encode("utf-8") for req in broker_requests
    ] + [b""]

    process = DummyProcess(stdout_lines, stderr_lines, returncode=0)

    async def fake_create_subprocess_exec(*_args, **_kwargs):
        return process

    async def control_handler(request):
        if request.get("x") == 2:
            raise RuntimeError("boom")
        return {"ok": True}

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    request = ExecutionRequest(source="return {}", working_dir="/workspace")
    result = await runner._run_container(
        ["docker"],
        request,
        timeout=1,
        control_handler=control_handler,
    )

    assert result.status == ExecutionStatus.SUCCESS

    payload_lines = [line for line in process.stdin.buffer.split(b"\n") if line.strip()]
    response_lines = [line.decode("utf-8") for line in payload_lines[1:]]
    responses = [json.loads(line) for line in response_lines]
    response_by_id = {resp.get("id"): resp for resp in responses if isinstance(resp, dict)}

    assert response_by_id["control_ok"]["event"] == "response"
    assert response_by_id["control_fail"]["event"] == "error"
    assert response_by_id["tool_ok"]["event"] == "done"


@pytest.mark.asyncio
async def test_run_container_extracts_result_from_stdout_fallback(monkeypatch):
    config = SandboxConfig(mount_current_dir=False, broker_transport="tcp")
    runner = ContainerRunner(config)

    result_payload = ExecutionResult.success(result={"ok": True}).to_json()
    stdout_lines = [
        f"noise{RESULT_START_MARKER}\n".encode("utf-8"),
        f"{result_payload}\n".encode("utf-8"),
        f"{RESULT_END_MARKER}tail\n".encode("utf-8"),
        b"",
    ]
    process = DummyProcess(stdout_lines, [b""], returncode=0)

    async def fake_create_subprocess_exec(*_args, **_kwargs):
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    request = ExecutionRequest(source="return {}", working_dir="/workspace")
    result = await runner._run_container(["docker"], request, timeout=1)

    assert result.status == ExecutionStatus.SUCCESS
    assert result.result == {"ok": True}


@pytest.mark.asyncio
async def test_run_container_exit_code_nonzero_without_output(monkeypatch):
    config = SandboxConfig(mount_current_dir=False, broker_transport="tcp")
    runner = ContainerRunner(config)

    process = DummyProcess([b""], [b""], returncode=2)

    async def fake_create_subprocess_exec(*_args, **_kwargs):
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    request = ExecutionRequest(source="return {}", working_dir="/workspace")
    result = await runner._run_container(["docker"], request, timeout=1)

    assert result.status == ExecutionStatus.ERROR
    assert result.exit_code == 2
    assert "Container exited with code 2" in result.error


@pytest.mark.asyncio
async def test_run_container_event_handler_exception(monkeypatch):
    config = SandboxConfig(mount_current_dir=False, broker_transport="stdio")
    runner = ContainerRunner(config)

    monkeypatch.setattr(
        "tactus.broker.server.HostToolRegistry.default", lambda: FakeToolRegistry({})
    )
    monkeypatch.setattr(
        "tactus.broker.server.OpenAIChatBackend", lambda api_key=None: FakeChatBackend()
    )

    result_payload = ExecutionResult.success(result={"ok": True}).to_json()
    stdout_lines = [
        f"{RESULT_START_MARKER}\n".encode("utf-8"),
        f"{result_payload}\n".encode("utf-8"),
        f"{RESULT_END_MARKER}\n".encode("utf-8"),
        b"",
    ]

    broker_requests = [
        {"id": "evt", "method": "events.emit", "params": {"event": {"type": "ping"}}}
    ]
    stderr_lines = [
        f"{STDIO_REQUEST_PREFIX}{json.dumps(req)}\n".encode("utf-8") for req in broker_requests
    ] + [b""]

    process = DummyProcess(stdout_lines, stderr_lines, returncode=0)

    async def fake_create_subprocess_exec(*_args, **_kwargs):
        return process

    def boom(_event):
        raise RuntimeError("boom")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    request = ExecutionRequest(source="return {}", working_dir="/workspace")
    result = await runner._run_container(["docker"], request, timeout=1, event_handler=boom)

    assert result.status == ExecutionStatus.SUCCESS


@pytest.mark.asyncio
async def test_run_container_send_event_writer_closed(monkeypatch):
    config = SandboxConfig(mount_current_dir=False, broker_transport="stdio")
    runner = ContainerRunner(config)

    monkeypatch.setattr(
        "tactus.broker.server.HostToolRegistry.default", lambda: FakeToolRegistry({})
    )
    monkeypatch.setattr(
        "tactus.broker.server.OpenAIChatBackend", lambda api_key=None: FakeChatBackend()
    )

    result_payload = ExecutionResult.success(result={"ok": True}).to_json()
    stdout_lines = [
        f"{RESULT_START_MARKER}\n".encode("utf-8"),
        f"{result_payload}\n".encode("utf-8"),
        f"{RESULT_END_MARKER}\n".encode("utf-8"),
        b"",
    ]

    broker_requests = [
        {"id": "evt", "method": "events.emit", "params": {"event": {"type": "ping"}}}
    ]
    stderr_lines = [
        f"{STDIO_REQUEST_PREFIX}{json.dumps(req)}\n".encode("utf-8") for req in broker_requests
    ] + [b""]

    process = DummyProcess(stdout_lines, stderr_lines, returncode=0)
    process.stdin = ClosedStdin()

    async def fake_create_subprocess_exec(*_args, **_kwargs):
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    request = ExecutionRequest(source="return {}", working_dir="/workspace")
    result = await runner._run_container(["docker"], request, timeout=1)

    assert result.status == ExecutionStatus.SUCCESS


@pytest.mark.asyncio
async def test_run_container_send_event_broken_pipe(monkeypatch):
    config = SandboxConfig(mount_current_dir=False, broker_transport="stdio")
    runner = ContainerRunner(config)

    monkeypatch.setattr(
        "tactus.broker.server.HostToolRegistry.default", lambda: FakeToolRegistry({})
    )
    monkeypatch.setattr(
        "tactus.broker.server.OpenAIChatBackend", lambda api_key=None: FakeChatBackend()
    )

    result_payload = ExecutionResult.success(result={"ok": True}).to_json()
    stdout_lines = [
        f"{RESULT_START_MARKER}\n".encode("utf-8"),
        f"{result_payload}\n".encode("utf-8"),
        f"{RESULT_END_MARKER}\n".encode("utf-8"),
        b"",
    ]

    broker_requests = [
        {"id": "evt", "method": "events.emit", "params": {"event": {"type": "ping"}}}
    ]
    stderr_lines = [
        f"{STDIO_REQUEST_PREFIX}{json.dumps(req)}\n".encode("utf-8") for req in broker_requests
    ] + [b""]

    process = DummyProcess(stdout_lines, stderr_lines, returncode=0)
    process.stdin = FlakyStdin(fail_on_write=True)

    async def fake_create_subprocess_exec(*_args, **_kwargs):
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    request = ExecutionRequest(source="return {}", working_dir="/workspace")
    result = await runner._run_container(["docker"], request, timeout=1)

    assert result.status == ExecutionStatus.SUCCESS


@pytest.mark.asyncio
async def test_run_container_uses_openai_key_from_backend_config(monkeypatch):
    config = SandboxConfig(mount_current_dir=False, broker_transport="stdio")
    runner = ContainerRunner(config)

    captured = {}

    def fake_openai_backend(api_key=None):
        captured["api_key"] = api_key
        return FakeChatBackend()

    monkeypatch.setattr(
        "tactus.broker.server.HostToolRegistry.default", lambda: FakeToolRegistry({})
    )
    monkeypatch.setattr("tactus.broker.server.OpenAIChatBackend", fake_openai_backend)

    result_payload = ExecutionResult.success(result={"ok": True}).to_json()
    stdout_lines = [
        f"{RESULT_START_MARKER}\n".encode("utf-8"),
        f"{result_payload}\n".encode("utf-8"),
        f"{RESULT_END_MARKER}\n".encode("utf-8"),
        b"",
    ]
    process = DummyProcess(stdout_lines, [b""], returncode=0)

    async def fake_create_subprocess_exec(*_args, **_kwargs):
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    request = ExecutionRequest(source="return {}", working_dir="/workspace")
    result = await runner._run_container(
        ["docker"],
        request,
        timeout=1,
        llm_backend_config={"openai_api_key": "sk-test"},
    )

    assert result.status == ExecutionStatus.SUCCESS
    assert captured["api_key"] == "sk-test"


@pytest.mark.asyncio
async def test_run_container_handles_multiple_results(monkeypatch):
    config = SandboxConfig(mount_current_dir=False, broker_transport="tcp")
    runner = ContainerRunner(config)

    result_payload = ExecutionResult.success(result={"ok": True}).to_json()
    stdout_lines = [
        f"{RESULT_START_MARKER}\n".encode("utf-8"),
        f"{result_payload}\n".encode("utf-8"),
        f"{RESULT_END_MARKER}\n".encode("utf-8"),
        f"{RESULT_START_MARKER}\n".encode("utf-8"),
        f"{result_payload}\n".encode("utf-8"),
        f"{RESULT_END_MARKER}\n".encode("utf-8"),
        b"",
    ]
    process = DummyProcess(stdout_lines, [b""], returncode=0)

    async def fake_create_subprocess_exec(*_args, **_kwargs):
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    request = ExecutionRequest(source="return {}", working_dir="/workspace")
    result = await runner._run_container(["docker"], request, timeout=1)

    assert result.status == ExecutionStatus.SUCCESS


@pytest.mark.asyncio
async def test_run_container_close_stdin_after_loop_errors(monkeypatch):
    config = SandboxConfig(mount_current_dir=False, broker_transport="tcp")
    runner = ContainerRunner(config)

    process = DummyProcess([b""], [b""], returncode=0)
    process.stdin = BrokenCloseStdin()

    async def fake_create_subprocess_exec(*_args, **_kwargs):
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    request = ExecutionRequest(source="return {}", working_dir="/workspace")
    result = await runner._run_container(["docker"], request, timeout=1)

    assert result.status == ExecutionStatus.SUCCESS
