import asyncio
import io
from datetime import datetime, timezone, timedelta

import pytest
from rich.console import Console

from tactus.cli.control import ControlCLI


@pytest.mark.asyncio
async def test_connect_missing_socket(monkeypatch):
    console_output = io.StringIO()
    cli = ControlCLI(socket_path="/tmp/missing.sock")
    cli.console = Console(file=console_output, force_terminal=False)

    async def boom(*_args, **_kwargs):
        raise FileNotFoundError

    monkeypatch.setattr("asyncio.open_unix_connection", boom)

    connected = await cli.connect()

    assert connected is False
    assert "Socket not found" in console_output.getvalue()


@pytest.mark.asyncio
async def test_connect_refused(monkeypatch):
    console_output = io.StringIO()
    cli = ControlCLI(socket_path="/tmp/socket.sock")
    cli.console = Console(file=console_output, force_terminal=False)

    async def boom(*_args, **_kwargs):
        raise ConnectionRefusedError

    monkeypatch.setattr("asyncio.open_unix_connection", boom)

    connected = await cli.connect()

    assert connected is False
    assert "Connection refused" in console_output.getvalue()


@pytest.mark.asyncio
async def test_connect_generic_error(monkeypatch):
    console_output = io.StringIO()
    cli = ControlCLI(socket_path="/tmp/socket.sock")
    cli.console = Console(file=console_output, force_terminal=False)

    async def boom(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("asyncio.open_unix_connection", boom)

    connected = await cli.connect()

    assert connected is False
    assert "Failed to connect" in console_output.getvalue()


@pytest.mark.asyncio
async def test_connect_success(monkeypatch):
    cli = ControlCLI(socket_path="/tmp/socket.sock")

    async def fake_connect(_path):
        return object(), object()

    monkeypatch.setattr("asyncio.open_unix_connection", fake_connect)

    connected = await cli.connect()

    assert connected is True
    assert cli._reader is not None
    assert cli._writer is not None


@pytest.mark.asyncio
async def test_handle_message_routes(monkeypatch):
    cli = ControlCLI()
    cli.console = Console(file=io.StringIO(), force_terminal=False)
    called = {"request": 0, "cancel": 0, "list": 0}

    async def fake_request(_message):
        called["request"] += 1

    def fake_cancel(_message):
        called["cancel"] += 1

    def fake_list(_message):
        called["list"] += 1

    cli._handle_request = fake_request
    cli._handle_cancellation = fake_cancel
    cli._handle_list_response = fake_list

    await cli._handle_message({"type": "control.request"})
    await cli._handle_message({"type": "control.cancelled"})
    await cli._handle_message({"type": "control.list_response"})
    await cli._handle_message({"type": "unknown"})

    assert called == {"request": 1, "cancel": 1, "list": 1}


@pytest.mark.asyncio
async def test_disconnect_handles_writer_errors():
    cli = ControlCLI()

    class ExplodingWriter:
        def close(self):
            raise RuntimeError("boom")

        async def wait_closed(self):
            raise RuntimeError("boom")

    cli._writer = ExplodingWriter()

    await cli.disconnect()


@pytest.mark.asyncio
async def test_disconnect_closes_writer():
    cli = ControlCLI()
    called = {"closed": False, "waited": False}

    class Writer:
        def close(self):
            called["closed"] = True

        async def wait_closed(self):
            called["waited"] = True

    cli._writer = Writer()

    await cli.disconnect()

    assert called["closed"] is True
    assert called["waited"] is True


@pytest.mark.asyncio
async def test_disconnect_no_writer_noop():
    cli = ControlCLI()
    cli._writer = None

    await cli.disconnect()


@pytest.mark.asyncio
async def test_handle_choice_request_auto_respond_matches():
    cli = ControlCLI(auto_respond="b")
    cli.console = Console(file=io.StringIO(), force_terminal=False)
    sent = {}

    async def fake_send(request_id, value):
        sent["id"] = request_id
        sent["value"] = value

    cli._send_response = fake_send

    await cli._handle_choice_request(
        {"request_id": "req"},
        options=[{"label": "A", "value": "a"}, {"label": "B", "value": "b"}],
        default_value=None,
    )

    assert sent["value"] == "b"


@pytest.mark.asyncio
async def test_handle_choice_request_auto_respond_falls_back_to_first():
    cli = ControlCLI(auto_respond="nope")
    cli.console = Console(file=io.StringIO(), force_terminal=False)
    sent = {}

    async def fake_send(request_id, value):
        sent["value"] = value

    cli._send_response = fake_send

    await cli._handle_choice_request(
        {"request_id": "req"},
        options=[{"label": "A", "value": "a"}, {"label": "B", "value": "b"}],
        default_value=None,
    )

    assert sent["value"] == "a"


@pytest.mark.asyncio
async def test_handle_choice_request_interactive_invalid_then_valid(monkeypatch):
    console_output = io.StringIO()
    cli = ControlCLI()
    cli.console = Console(file=console_output, force_terminal=False)
    sent = {}

    answers = iter(["bad", "3", "2"])
    monkeypatch.setattr("tactus.cli.control.Prompt.ask", lambda *_a, **_k: next(answers))

    async def fake_send(request_id, value):
        sent["value"] = value

    cli._send_response = fake_send

    await cli._handle_choice_request(
        {"request_id": "req"},
        options=[{"label": "A", "value": "a"}, {"label": "B", "value": "b"}],
        default_value=None,
    )

    assert sent["value"] == "b"
    assert "Invalid selection" in console_output.getvalue()


@pytest.mark.asyncio
async def test_handle_choice_request_interactive_default_value(monkeypatch):
    cli = ControlCLI()
    cli.console = Console(file=io.StringIO(), force_terminal=False)
    sent = {}

    monkeypatch.setattr("tactus.cli.control.Prompt.ask", lambda *_a, **_k: "1")

    async def fake_send(request_id, value):
        sent["value"] = value

    cli._send_response = fake_send

    await cli._handle_choice_request(
        {"request_id": "req"},
        options=[{"label": "A", "value": "a"}],
        default_value="a",
    )

    assert sent["value"] == "a"


@pytest.mark.asyncio
async def test_handle_choice_request_default_value_missing_falls_back(monkeypatch):
    cli = ControlCLI()
    cli.console = Console(file=io.StringIO(), force_terminal=False)
    sent = {}
    observed = {}

    def fake_prompt(*_a, **kwargs):
        observed["default"] = kwargs.get("default")
        return "1"

    monkeypatch.setattr("tactus.cli.control.Prompt.ask", fake_prompt)

    async def fake_send(request_id, value):
        sent["value"] = value

    cli._send_response = fake_send

    await cli._handle_choice_request(
        {"request_id": "req"},
        options=[{"label": "A", "value": "a"}, {"label": "B", "value": "b"}],
        default_value="missing",
    )

    assert observed["default"] == "1"
    assert sent["value"] == "a"


@pytest.mark.asyncio
async def test_handle_input_request_auto_respond():
    cli = ControlCLI(auto_respond="auto")
    cli.console = Console(file=io.StringIO(), force_terminal=False)
    sent = {}

    async def fake_send(request_id, value):
        sent["value"] = value

    cli._send_response = fake_send

    await cli._handle_input_request({"request_id": "req"}, default_value=None)

    assert sent["value"] == "auto"


@pytest.mark.asyncio
async def test_handle_input_request_prompt(monkeypatch):
    cli = ControlCLI()
    cli.console = Console(file=io.StringIO(), force_terminal=False)
    sent = {}

    monkeypatch.setattr("tactus.cli.control.Prompt.ask", lambda *_a, **_k: "value")

    async def fake_send(request_id, value):
        sent["value"] = value

    cli._send_response = fake_send

    await cli._handle_input_request({"request_id": "req"}, default_value="default")

    assert sent["value"] == "value"


@pytest.mark.asyncio
async def test_send_response_handles_write_failure(monkeypatch):
    console_output = io.StringIO()
    cli = ControlCLI()
    cli.console = Console(file=console_output, force_terminal=False)
    cli._writer = object()

    async def boom(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("tactus.cli.control.write_message", boom)

    await cli._send_response("req", "value")

    assert "Failed to send response" in console_output.getvalue()


@pytest.mark.asyncio
async def test_send_response_success(monkeypatch):
    console_output = io.StringIO()
    cli = ControlCLI()
    cli.console = Console(file=console_output, force_terminal=False)
    cli._writer = object()
    sent = {}

    async def fake_write(_writer, message):
        sent.update(message)

    monkeypatch.setattr("tactus.cli.control.write_message", fake_write)

    await cli._send_response("req", "value")

    assert sent["request_id"] == "req"
    assert "Response sent" in console_output.getvalue()


def test_handle_list_response_no_requests():
    console_output = io.StringIO()
    cli = ControlCLI()
    cli.console = Console(file=console_output, force_terminal=False)

    cli._handle_list_response({"requests": []})

    assert "No pending requests" in console_output.getvalue()


def test_handle_list_response_with_requests():
    console_output = io.StringIO()
    cli = ControlCLI()
    cli.console = Console(file=console_output, force_terminal=False)

    cli._handle_list_response(
        {"requests": [{"request_id": "abc12345", "request_type": "input", "message": "hello"}]}
    )

    assert "Pending Requests" in console_output.getvalue()


def test_handle_cancellation_prints_reason():
    console_output = io.StringIO()
    cli = ControlCLI()
    cli.console = Console(file=console_output, force_terminal=False)

    cli._handle_cancellation({"request_id": "req", "reason": "timeout"})

    assert "cancelled" in console_output.getvalue()


@pytest.mark.asyncio
async def test_handle_request_unknown_type_prints_warning():
    console_output = io.StringIO()
    cli = ControlCLI()
    cli.console = Console(file=console_output, force_terminal=False)

    request = {
        "request_id": "req",
        "procedure_name": "Proc",
        "request_type": "unknown",
        "message": "hello",
        "started_at": datetime.now(timezone.utc).isoformat(),
    }

    await cli._handle_request(request)

    assert "Unknown request type" in console_output.getvalue()


@pytest.mark.asyncio
async def test_handle_request_elapsed_formats_minutes(monkeypatch):
    console_output = io.StringIO()
    cli = ControlCLI()
    cli.console = Console(file=console_output, force_terminal=False)

    started_at = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    request = {
        "request_id": "req",
        "procedure_name": "Proc",
        "request_type": "approval",
        "message": "hello",
        "started_at": started_at,
    }

    async def fake_approval(_request, _options, _default):
        return None

    cli._handle_approval_request = fake_approval

    await cli._handle_request(request)

    assert "minutes ago" in console_output.getvalue()


@pytest.mark.asyncio
async def test_handle_request_elapsed_formats_hours(monkeypatch):
    console_output = io.StringIO()
    cli = ControlCLI()
    cli.console = Console(file=console_output, force_terminal=False)

    started_at = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    request = {
        "request_id": "req",
        "procedure_name": "Proc",
        "request_type": "approval",
        "message": "hello",
        "started_at": started_at,
    }

    async def fake_approval(_request, _options, _default):
        return None

    cli._handle_approval_request = fake_approval

    await cli._handle_request(request)

    assert "hours ago" in console_output.getvalue()


@pytest.mark.asyncio
async def test_handle_approval_request_prompt_default(monkeypatch):
    cli = ControlCLI()
    cli.console = Console(file=io.StringIO(), force_terminal=False)
    sent = {}

    monkeypatch.setattr("tactus.cli.control.Confirm.ask", lambda *_a, **_k: True)

    async def fake_send(request_id, value):
        sent["value"] = value

    cli._send_response = fake_send

    await cli._handle_approval_request({"request_id": "req"}, [], default_value=True)

    assert sent["value"] is True


@pytest.mark.asyncio
async def test_handle_approval_request_prompt_no_default(monkeypatch):
    cli = ControlCLI()
    cli.console = Console(file=io.StringIO(), force_terminal=False)
    sent = {}

    monkeypatch.setattr("tactus.cli.control.Confirm.ask", lambda *_a, **_k: False)

    async def fake_send(request_id, value):
        sent["value"] = value

    cli._send_response = fake_send

    await cli._handle_approval_request({"request_id": "req"}, [], default_value=None)

    assert sent["value"] is False


@pytest.mark.asyncio
async def test_handle_approval_request_auto_respond():
    cli = ControlCLI(auto_respond="yes")
    cli.console = Console(file=io.StringIO(), force_terminal=False)
    sent = {}

    async def fake_send(request_id, value):
        sent["value"] = value

    cli._send_response = fake_send

    await cli._handle_approval_request({"request_id": "req"}, [], default_value=None)

    assert sent["value"] is True


@pytest.mark.asyncio
async def test_handle_request_branches_with_auto_respond(monkeypatch):
    cli = ControlCLI(auto_respond="yes")
    cli.console = Console(file=io.StringIO(), force_terminal=False)
    called = {"approval": 0, "choice": 0, "input": 0}

    async def fake_approval(request, options, default):
        called["approval"] += 1

    async def fake_choice(request, options, default):
        called["choice"] += 1

    async def fake_input(request, default):
        called["input"] += 1

    cli._handle_approval_request = fake_approval
    cli._handle_choice_request = fake_choice
    cli._handle_input_request = fake_input

    base = {
        "request_id": "req",
        "request_type": "approval",
        "message": "m",
        "procedure_name": "proc",
    }

    await cli._handle_request(base)
    base["request_type"] = "choice"
    await cli._handle_request(base)
    base["request_type"] = "input"
    await cli._handle_request(base)

    assert called == {"approval": 1, "choice": 1, "input": 1}


@pytest.mark.asyncio
async def test_list_requests_success(monkeypatch):
    cli = ControlCLI()
    cli.console = Console(file=io.StringIO(), force_terminal=False)

    async def fake_connect():
        cli._reader = object()
        cli._writer = object()
        return True

    async def fake_disconnect():
        return None

    async def fake_read(_reader):
        return {"type": "control.list_response", "requests": []}

    async def fake_write(_writer, _message):
        return None

    monkeypatch.setattr(cli, "connect", fake_connect)
    monkeypatch.setattr(cli, "disconnect", fake_disconnect)
    monkeypatch.setattr("tactus.cli.control.read_message", fake_read)
    monkeypatch.setattr("tactus.cli.control.write_message", fake_write)

    await cli.list_requests()


@pytest.mark.asyncio
async def test_list_requests_non_list_response(monkeypatch):
    cli = ControlCLI()
    cli.console = Console(file=io.StringIO(), force_terminal=False)
    handled = {"called": False}

    async def fake_connect():
        cli._reader = object()
        cli._writer = object()
        return True

    async def fake_disconnect():
        return None

    async def fake_read(_reader):
        return {"type": "other"}

    async def fake_write(_writer, _message):
        return None

    def fake_handle(_message):
        handled["called"] = True

    monkeypatch.setattr(cli, "connect", fake_connect)
    monkeypatch.setattr(cli, "disconnect", fake_disconnect)
    monkeypatch.setattr("tactus.cli.control.read_message", fake_read)
    monkeypatch.setattr("tactus.cli.control.write_message", fake_write)
    monkeypatch.setattr(cli, "_handle_list_response", fake_handle)

    await cli.list_requests()

    assert handled["called"] is False


@pytest.mark.asyncio
async def test_list_requests_connect_fails(monkeypatch):
    cli = ControlCLI()
    cli.console = Console(file=io.StringIO(), force_terminal=False)

    async def fake_connect():
        return False

    monkeypatch.setattr(cli, "connect", fake_connect)

    await cli.list_requests()


@pytest.mark.asyncio
async def test_list_requests_handles_exception(monkeypatch):
    console_output = io.StringIO()
    cli = ControlCLI()
    cli.console = Console(file=console_output, force_terminal=False)

    async def fake_connect():
        cli._reader = object()
        cli._writer = object()
        return True

    async def fake_disconnect():
        return None

    async def fake_write(_writer, _message):
        raise RuntimeError("boom")

    monkeypatch.setattr(cli, "connect", fake_connect)
    monkeypatch.setattr(cli, "disconnect", fake_disconnect)
    monkeypatch.setattr("tactus.cli.control.write_message", fake_write)

    await cli.list_requests()

    assert "Failed to list requests" in console_output.getvalue()


@pytest.mark.asyncio
async def test_watch_mode_connect_fails(monkeypatch):
    cli = ControlCLI()
    cli.console = Console(file=io.StringIO(), force_terminal=False)

    async def fake_connect():
        return False

    monkeypatch.setattr(cli, "connect", fake_connect)

    await cli.watch_mode()


@pytest.mark.asyncio
async def test_watch_mode_eof_disconnects(monkeypatch):
    console_output = io.StringIO()
    cli = ControlCLI()
    cli.console = Console(file=console_output, force_terminal=False)
    cli._reader = object()
    cli._running = True
    called = {"disconnected": False}

    async def fake_connect():
        return True

    async def fake_disconnect():
        called["disconnected"] = True

    async def fake_read(_reader):
        raise EOFError

    monkeypatch.setattr(cli, "connect", fake_connect)
    monkeypatch.setattr(cli, "disconnect", fake_disconnect)
    monkeypatch.setattr("tactus.cli.control.read_message", fake_read)

    await cli.watch_mode()

    assert called["disconnected"] is True


@pytest.mark.asyncio
async def test_watch_mode_handles_message(monkeypatch):
    cli = ControlCLI()
    cli.console = Console(file=io.StringIO(), force_terminal=False)
    cli._reader = object()
    cli._running = True
    handled = {"called": False}

    async def fake_connect():
        return True

    async def fake_disconnect():
        return None

    async def fake_read(_reader):
        if not handled["called"]:
            return {"type": "control.list_response", "requests": []}
        raise EOFError

    async def fake_handle(_message):
        handled["called"] = True
        cli._running = False

    monkeypatch.setattr(cli, "connect", fake_connect)
    monkeypatch.setattr(cli, "disconnect", fake_disconnect)
    monkeypatch.setattr("tactus.cli.control.read_message", fake_read)
    monkeypatch.setattr(cli, "_handle_message", fake_handle)

    await cli.watch_mode()

    assert handled["called"] is True


@pytest.mark.asyncio
async def test_watch_mode_incomplete_read_disconnects(monkeypatch):
    console_output = io.StringIO()
    cli = ControlCLI()
    cli.console = Console(file=console_output, force_terminal=False)
    cli._reader = object()
    cli._running = True

    async def fake_connect():
        return True

    async def fake_disconnect():
        return None

    async def fake_read(_reader):
        raise asyncio.IncompleteReadError(partial=b"", expected=1)

    monkeypatch.setattr(cli, "connect", fake_connect)
    monkeypatch.setattr(cli, "disconnect", fake_disconnect)
    monkeypatch.setattr("tactus.cli.control.read_message", fake_read)

    await cli.watch_mode()

    assert "Connection closed by runtime" in console_output.getvalue()


@pytest.mark.asyncio
async def test_watch_mode_incomplete_read_subclass(monkeypatch):
    console_output = io.StringIO()
    cli = ControlCLI()
    cli.console = Console(file=console_output, force_terminal=False)
    cli._reader = object()

    class FakeIncompleteRead(asyncio.IncompleteReadError):
        pass

    async def fake_connect():
        return True

    async def fake_disconnect():
        return None

    async def fake_read(_reader):
        raise FakeIncompleteRead(partial=b"", expected=1)

    monkeypatch.setattr(cli, "connect", fake_connect)
    monkeypatch.setattr(cli, "disconnect", fake_disconnect)
    monkeypatch.setattr("tactus.cli.control.read_message", fake_read)

    await cli.watch_mode()

    assert "Connection closed by runtime" in console_output.getvalue()


@pytest.mark.asyncio
async def test_watch_mode_keyboard_interrupt(monkeypatch):
    console_output = io.StringIO()
    cli = ControlCLI()
    cli.console = Console(file=console_output, force_terminal=False)
    cli._reader = object()
    cli._running = True

    async def fake_connect():
        return True

    async def fake_disconnect():
        return None

    async def fake_read(_reader):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "connect", fake_connect)
    monkeypatch.setattr(cli, "disconnect", fake_disconnect)
    monkeypatch.setattr("tactus.cli.control.read_message", fake_read)

    await cli.watch_mode()

    assert "Disconnecting" in console_output.getvalue()


@pytest.mark.asyncio
async def test_main_calls_watch_mode(monkeypatch):
    called = {"watch": False}

    async def fake_watch(self):
        called["watch"] = True

    monkeypatch.setattr("tactus.cli.control.ControlCLI.watch_mode", fake_watch)

    from tactus.cli.control import main

    await main("/tmp/socket.sock", None)

    assert called["watch"] is True
