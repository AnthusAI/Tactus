from datetime import datetime, timedelta, timezone

import pytest

from tactus.adapters.channels.cli import CLIControlChannel, format_time_ago
from tactus.protocols.control import (
    ControlOption,
    ControlInteraction,
    ControlRequest,
    ControlRequestItem,
    ControlRequestType,
)


class DummyConsole:
    def __init__(self):
        self.messages = []

    def print(self, *args, **kwargs):
        self.messages.append(" ".join(str(arg) for arg in args))
        return None


def _make_request():
    return ControlRequest(
        request_id="req",
        procedure_id="proc",
        procedure_name="name",
        invocation_id="inv",
        started_at=datetime.now(timezone.utc),
        request_type=ControlRequestType.INPUT,
        message="Need input",
    )


def test_format_time_ago_ranges():
    now = datetime.now(timezone.utc)
    assert format_time_ago(now - timedelta(seconds=5)) == "5 seconds"
    assert format_time_ago(now - timedelta(minutes=2)) == "2 minutes"
    assert format_time_ago(now - timedelta(hours=1)) == "1 hour"
    assert format_time_ago(now - timedelta(days=3)) == "3 days"
    assert format_time_ago(now - timedelta(hours=26)) == "1 day"
    assert format_time_ago(now - timedelta(days=1)) == "1 day"


@pytest.mark.asyncio
async def test_channel_properties_and_initialize(monkeypatch, caplog):
    channel = CLIControlChannel(console=DummyConsole())
    assert channel.channel_id == "cli"
    caps = channel.capabilities
    assert caps.supports_approval is True
    assert caps.is_synchronous is True

    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    await channel.initialize()
    assert any("stdin is not a tty" in record.message for record in caplog.records)


@pytest.mark.asyncio
async def test_channel_initialize_with_tty(monkeypatch, caplog):
    channel = CLIControlChannel(console=DummyConsole())
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    await channel.initialize()
    assert not any("stdin is not a tty" in record.message for record in caplog.records)


def test_display_request_renders_sections():
    channel = CLIControlChannel(console=DummyConsole())
    request = _make_request()
    request.subject = "Account 42"
    request.input_summary = {"name": "Ada"}
    request.prior_interactions = [
        ControlInteraction(
            request_type="approval",
            message="Approve?",
            response_value=True,
            responded_at=datetime.now(timezone.utc),
            channel_id="cli",
        )
    ]

    channel._display_request(request)

    joined = " ".join(channel.console.messages)
    assert "Account 42" in joined
    assert "Previous decisions" in joined


def test_display_request_without_optional_sections():
    channel = CLIControlChannel(console=DummyConsole())
    request = _make_request()
    request.subject = None
    request.input_summary = {}
    request.prior_interactions = []

    channel._display_request(request)

    joined = " ".join(channel.console.messages)
    assert "Previous decisions" not in joined


def test_handle_input_with_options(monkeypatch):
    channel = CLIControlChannel(console=DummyConsole())

    options = [
        ControlOption(label="Yes", value=True),
        ControlOption(label="No", value=False),
    ]
    request = _make_request()
    request.options = options

    monkeypatch.setattr("tactus.adapters.channels.cli.Prompt.ask", lambda *args, **kwargs: "1")
    assert channel._handle_input(request) is True


def test_handle_approval_cancelled_before_prompt():
    channel = CLIControlChannel(console=DummyConsole())
    channel._cancel_event.set()
    assert channel._handle_approval(_make_request()) is None


def test_handle_options_renders_description(monkeypatch):
    channel = CLIControlChannel(console=DummyConsole())
    options = [ControlOption(label="One", value="a", description="Desc")]

    monkeypatch.setattr("tactus.adapters.channels.cli.Prompt.ask", lambda *args, **kwargs: "1")

    assert channel._handle_options(options, None) == "a"
    assert any("Desc" in msg for msg in channel.console.messages)


def test_handle_review_paths(monkeypatch):
    channel = CLIControlChannel(console=DummyConsole())
    request = _make_request()

    answers = iter(["1", "2", "edit feedback", "3", "reject feedback"])

    def fake_prompt(*args, **kwargs):
        return next(answers)

    monkeypatch.setattr("tactus.adapters.channels.cli.Prompt.ask", fake_prompt)

    assert channel._handle_review(request)["decision"] == "approved"
    result = channel._handle_review(request)
    assert result["feedback"] == "edit feedback"
    result = channel._handle_review(request)
    assert result["decision"] == "rejected"


def test_handle_review_cancelled_before_prompt():
    channel = CLIControlChannel(console=DummyConsole())
    channel._cancel_event.set()
    assert channel._handle_review(_make_request()) is None


def test_handle_review_invalid_choice_then_approve(monkeypatch):
    channel = CLIControlChannel(console=DummyConsole())
    request = _make_request()

    answers = iter(["invalid", "approve"])
    monkeypatch.setattr(
        "tactus.adapters.channels.cli.Prompt.ask", lambda *args, **kwargs: next(answers)
    )

    assert channel._handle_review(request)["decision"] == "approved"


def test_handle_review_cancelled_after_edit_feedback(monkeypatch):
    channel = CLIControlChannel(console=DummyConsole())
    request = _make_request()

    def fake_prompt(text, *args, **kwargs):
        if text == "Your decision":
            return "2"
        channel._cancel_event.set()
        return "feedback"

    monkeypatch.setattr("tactus.adapters.channels.cli.Prompt.ask", fake_prompt)

    assert channel._handle_review(request) is None


def test_handle_review_cancelled_after_reject_feedback(monkeypatch):
    channel = CLIControlChannel(console=DummyConsole())
    request = _make_request()

    def fake_prompt(text, *args, **kwargs):
        if text == "Your decision":
            return "3"
        channel._cancel_event.set()
        return "feedback"

    monkeypatch.setattr("tactus.adapters.channels.cli.Prompt.ask", fake_prompt)

    assert channel._handle_review(request) is None


def test_handle_review_invalid_choice_then_cancel(monkeypatch):
    channel = CLIControlChannel(console=DummyConsole())
    request = _make_request()

    def fake_prompt(*args, **kwargs):
        return "invalid"

    monkeypatch.setattr("tactus.adapters.channels.cli.Prompt.ask", fake_prompt)

    calls = {"count": 0}

    def fake_is_cancelled():
        calls["count"] += 1
        return calls["count"] >= 4

    monkeypatch.setattr(channel, "is_cancelled", fake_is_cancelled)

    assert channel._handle_review(request) is None


def test_handle_review_eof_returns_none(monkeypatch):
    channel = CLIControlChannel(console=DummyConsole())
    request = _make_request()

    def fake_prompt(*args, **kwargs):
        raise EOFError

    monkeypatch.setattr("tactus.adapters.channels.cli.Prompt.ask", fake_prompt)

    assert channel._handle_review(request) is None


def test_handle_escalation_ack(monkeypatch):
    channel = CLIControlChannel(console=DummyConsole())
    request = _make_request()
    monkeypatch.setattr("tactus.adapters.channels.cli.Confirm.ask", lambda *args, **kwargs: True)
    assert channel._handle_escalation(request) is True


def test_handle_inputs_batched(monkeypatch):
    channel = CLIControlChannel(console=DummyConsole())
    request = _make_request()
    request.request_type = ControlRequestType.INPUTS
    request.items = [
        ControlRequestItem(
            item_id="a",
            label="First",
            request_type=ControlRequestType.INPUT,
            message="First input",
            default_value="one",
        ),
        ControlRequestItem(
            item_id="b",
            label="Second",
            request_type=ControlRequestType.INPUT,
            message="Second input",
            default_value="two",
        ),
    ]

    answers = iter(["one", "two"])
    monkeypatch.setattr(
        "tactus.adapters.channels.cli.Prompt.ask", lambda *args, **kwargs: next(answers)
    )

    result = channel._handle_inputs(request)
    assert result["a"] == "one"
    assert result["b"] == "two"


def test_handle_inputs_cancelled_before_start():
    channel = CLIControlChannel(console=DummyConsole())
    request = _make_request()
    request.request_type = ControlRequestType.INPUTS
    request.items = [
        ControlRequestItem(
            item_id="a",
            label="First",
            request_type=ControlRequestType.INPUT,
            message="First input",
        )
    ]

    channel._cancel_event.set()
    assert channel._handle_inputs(request) is None


def test_handle_inputs_cancelled_mid_loop(monkeypatch):
    channel = CLIControlChannel(console=DummyConsole())
    request = _make_request()
    request.request_type = ControlRequestType.INPUTS
    request.items = [
        ControlRequestItem(
            item_id="a",
            label="First",
            request_type=ControlRequestType.INPUT,
            message="First input",
        ),
        ControlRequestItem(
            item_id="b",
            label="Second",
            request_type=ControlRequestType.INPUT,
            message="Second input",
        ),
    ]

    def fake_prompt(*args, **kwargs):
        channel._cancel_event.set()
        return "value"

    monkeypatch.setattr("tactus.adapters.channels.cli.Prompt.ask", fake_prompt)

    assert channel._handle_inputs(request) is None


def test_handle_inputs_approval_default(monkeypatch):
    channel = CLIControlChannel(console=DummyConsole())
    request = _make_request()
    request.request_type = ControlRequestType.INPUTS
    request.items = [
        ControlRequestItem(
            item_id="approve",
            label="Approve",
            request_type=ControlRequestType.APPROVAL,
            message="Approve?",
            default_value=True,
        )
    ]

    monkeypatch.setattr("tactus.adapters.channels.cli.Confirm.ask", lambda *args, **kwargs: True)

    result = channel._handle_inputs(request)
    assert result["approve"] is True


def test_handle_inputs_multiline_placeholder_and_review(monkeypatch):
    channel = CLIControlChannel(console=DummyConsole())
    request = _make_request()
    request.request_type = ControlRequestType.INPUTS
    request.items = [
        ControlRequestItem(
            item_id="note",
            label="Note",
            request_type=ControlRequestType.INPUT,
            message="Note",
            metadata={"placeholder": "hint"},
        ),
        ControlRequestItem(
            item_id="review",
            label="Review",
            request_type=ControlRequestType.REVIEW,
            message="Review?",
        ),
    ]

    answers = iter(["ok", "1"])

    def fake_prompt(*args, **kwargs):
        return next(answers)

    monkeypatch.setattr("tactus.adapters.channels.cli.Prompt.ask", fake_prompt)

    result = channel._handle_inputs(request)
    assert result["note"] == "ok"
    assert result["review"]["decision"] == "approved"


def test_handle_inputs_skips_optional_empty_value(monkeypatch):
    channel = CLIControlChannel(console=DummyConsole())
    request = _make_request()
    request.request_type = ControlRequestType.INPUTS
    request.items = [
        ControlRequestItem(
            item_id="opt",
            label="Optional",
            request_type=ControlRequestType.INPUT,
            message="Optional",
            required=False,
        )
    ]

    monkeypatch.setattr("tactus.adapters.channels.cli.Prompt.ask", lambda *args, **kwargs: "")

    result = channel._handle_inputs(request)
    assert "opt" not in result


def test_handle_inputs_cancelled_before_summary(monkeypatch):
    channel = CLIControlChannel(console=DummyConsole())
    request = _make_request()
    request.request_type = ControlRequestType.INPUTS
    request.items = [
        ControlRequestItem(
            item_id="a",
            label="First",
            request_type=ControlRequestType.INPUT,
            message="First input",
        )
    ]

    def fake_prompt(*args, **kwargs):
        channel._cancel_event.set()
        return "value"

    monkeypatch.setattr("tactus.adapters.channels.cli.Prompt.ask", fake_prompt)

    assert channel._handle_inputs(request) is None


def test_handle_inputs_cancelled_before_second_item(monkeypatch):
    class CancelAfterSpacing(DummyConsole):
        def __init__(self, target):
            super().__init__()
            self.target = target
            self.calls = 0

        def print(self, *args, **kwargs):
            super().print(*args, **kwargs)
            if not args:
                self.calls += 1
                if self.calls == 2:
                    self.target._cancel_event.set()

    channel = CLIControlChannel(console=DummyConsole())
    cancel_console = CancelAfterSpacing(channel)
    channel.console = cancel_console

    request = _make_request()
    request.request_type = ControlRequestType.INPUTS
    request.items = [
        ControlRequestItem(
            item_id="a",
            label="First",
            request_type=ControlRequestType.INPUT,
            message="First input",
        ),
        ControlRequestItem(
            item_id="b",
            label="Second",
            request_type=ControlRequestType.INPUT,
            message="Second input",
        ),
    ]

    monkeypatch.setattr("tactus.adapters.channels.cli.Prompt.ask", lambda *args, **kwargs: "value")

    assert channel._handle_inputs(request) is None


def test_handle_inputs_multiline_cancel_mid_loop(monkeypatch):
    channel = CLIControlChannel(console=DummyConsole())
    request = _make_request()
    request.request_type = ControlRequestType.INPUTS
    request.items = [
        ControlRequestItem(
            item_id="note",
            label="Note",
            request_type=ControlRequestType.INPUT,
            message="Enter note",
            metadata={"multiline": True},
        )
    ]

    def fake_prompt(*args, **kwargs):
        channel._cancel_event.set()
        return "line"

    monkeypatch.setattr("tactus.adapters.channels.cli.Prompt.ask", fake_prompt)

    assert channel._handle_inputs(request) is None


def test_handle_inputs_review_edit(monkeypatch):
    channel = CLIControlChannel(console=DummyConsole())
    request = _make_request()
    request.request_type = ControlRequestType.INPUTS
    request.items = [
        ControlRequestItem(
            item_id="review",
            label="Review",
            request_type=ControlRequestType.REVIEW,
            message="Review item",
        )
    ]

    answers = iter(["2", "change this"])
    monkeypatch.setattr(
        "tactus.adapters.channels.cli.Prompt.ask", lambda *args, **kwargs: next(answers)
    )

    result = channel._handle_inputs(request)
    assert result["review"]["decision"] == "approved"
    assert result["review"]["feedback"] == "change this"


def test_handle_inputs_prompt_eof_returns_none(monkeypatch):
    channel = CLIControlChannel(console=DummyConsole())
    request = _make_request()
    request.request_type = ControlRequestType.INPUTS
    request.items = [
        ControlRequestItem(
            item_id="a",
            label="First",
            request_type=ControlRequestType.INPUT,
            message="First input",
        )
    ]

    def fake_prompt(*args, **kwargs):
        raise EOFError

    monkeypatch.setattr("tactus.adapters.channels.cli.Prompt.ask", fake_prompt)

    assert channel._handle_inputs(request) is None


def test_handle_inputs_skip_summary_when_cancelled_after_spacing(monkeypatch):
    channel = CLIControlChannel(console=DummyConsole())
    calls = {"count": 0}

    def fake_is_cancelled():
        calls["count"] += 1
        return calls["count"] >= 4

    monkeypatch.setattr(channel, "is_cancelled", fake_is_cancelled)

    request = _make_request()
    request.request_type = ControlRequestType.INPUTS
    request.items = [
        ControlRequestItem(
            item_id="a",
            label="First",
            request_type=ControlRequestType.INPUT,
            message="First input",
        )
    ]

    monkeypatch.setattr("tactus.adapters.channels.cli.Prompt.ask", lambda *args, **kwargs: "value")

    assert channel._handle_inputs(request) is None


def test_handle_options_invalid_then_valid(monkeypatch):
    channel = CLIControlChannel(console=DummyConsole())
    options = [ControlOption(label="One", value="a"), ControlOption(label="Two", value="b")]
    answers = iter(["zero", "3", "2"])

    monkeypatch.setattr(
        "tactus.adapters.channels.cli.Prompt.ask", lambda *args, **kwargs: next(answers)
    )

    assert channel._handle_options(options, None) == "b"
    assert any("Invalid input" in msg for msg in channel.console.messages)
    assert any("Invalid choice" in msg for msg in channel.console.messages)


def test_handle_options_eof_returns_none(monkeypatch):
    channel = CLIControlChannel(console=DummyConsole())
    options = [ControlOption(label="One", value="a")]

    def fake_prompt(*args, **kwargs):
        raise EOFError

    monkeypatch.setattr("tactus.adapters.channels.cli.Prompt.ask", fake_prompt)

    assert channel._handle_options(options, None) is None


def test_handle_approval_handles_cancel(monkeypatch):
    channel = CLIControlChannel(console=DummyConsole())

    def fake_confirm(*args, **kwargs):
        raise EOFError

    monkeypatch.setattr("tactus.adapters.channels.cli.Confirm.ask", fake_confirm)
    assert channel._handle_approval(_make_request()) is None


def test_handle_input_freeform(monkeypatch):
    channel = CLIControlChannel(console=DummyConsole())
    request = _make_request()
    request.options = []

    monkeypatch.setattr("tactus.adapters.channels.cli.Prompt.ask", lambda *args, **kwargs: "value")
    assert channel._handle_input(request) == "value"


def test_handle_input_cancelled_before_prompt():
    channel = CLIControlChannel(console=DummyConsole())
    channel._cancel_event.set()
    assert channel._handle_input(_make_request()) is None


def test_handle_escalation_cancelled(monkeypatch):
    channel = CLIControlChannel(console=DummyConsole())
    channel._cancel_event.set()
    assert channel._handle_escalation(_make_request()) is None


def test_handle_inputs_empty_items():
    channel = CLIControlChannel(console=DummyConsole())
    request = _make_request()
    request.request_type = ControlRequestType.INPUTS
    request.items = []

    result = channel._handle_inputs(request)
    assert result == {}
    assert any("No items found" in msg for msg in channel.console.messages)


def test_handle_inputs_select(monkeypatch):
    channel = CLIControlChannel(console=DummyConsole())
    request = _make_request()
    request.request_type = ControlRequestType.INPUTS
    request.items = [
        ControlRequestItem(
            item_id="choice",
            label="Pick",
            request_type=ControlRequestType.SELECT,
            message="Pick one",
            options=[ControlOption(label="A", value="a")],
            default_value="1",
        )
    ]

    monkeypatch.setattr("tactus.adapters.channels.cli.Prompt.ask", lambda *args, **kwargs: "1")

    result = channel._handle_inputs(request)
    assert result["choice"] == "a"


def test_handle_inputs_multiline(monkeypatch):
    channel = CLIControlChannel(console=DummyConsole())
    request = _make_request()
    request.request_type = ControlRequestType.INPUTS
    request.items = [
        ControlRequestItem(
            item_id="note",
            label="Note",
            request_type=ControlRequestType.INPUT,
            message="Enter note",
            metadata={"multiline": True},
        )
    ]

    answers = iter(["line1", "line2", None])

    def fake_prompt(*args, **kwargs):
        value = next(answers)
        if value is None:
            raise EOFError
        return value

    monkeypatch.setattr("tactus.adapters.channels.cli.Prompt.ask", fake_prompt)

    result = channel._handle_inputs(request)
    assert result["note"] == "line1\nline2"


def test_handle_inputs_review(monkeypatch):
    channel = CLIControlChannel(console=DummyConsole())
    request = _make_request()
    request.request_type = ControlRequestType.INPUTS
    request.items = [
        ControlRequestItem(
            item_id="review",
            label="Review",
            request_type=ControlRequestType.REVIEW,
            message="Review item",
        )
    ]

    answers = iter(["3", "needs work"])

    monkeypatch.setattr(
        "tactus.adapters.channels.cli.Prompt.ask", lambda *args, **kwargs: next(answers)
    )

    result = channel._handle_inputs(request)
    assert result["review"]["decision"] == "rejected"
    assert result["review"]["feedback"] == "needs work"


def test_handle_inputs_custom_type_and_summary(monkeypatch):
    channel = CLIControlChannel(console=DummyConsole())
    request = _make_request()
    request.request_type = ControlRequestType.INPUTS
    request.items = [
        ControlRequestItem(
            item_id="custom",
            label="Custom",
            request_type=ControlRequestType.CUSTOM,
            message="Custom input",
            required=True,
        )
    ]

    monkeypatch.setattr("tactus.adapters.channels.cli.Prompt.ask", lambda *args, **kwargs: "x" * 80)

    result = channel._handle_inputs(request)
    assert result["custom"] == "x" * 80
    assert any("Summary" in msg for msg in channel.console.messages)


def test_handle_inputs_summary_handles_list_values_and_missing_labels(monkeypatch):
    class SummaryEmptyItems(list):
        def __init__(self, items):
            super().__init__(items)
            self._iteration_count = 0

        def __iter__(self):
            self._iteration_count += 1
            if self._iteration_count >= 3:
                return iter([])
            return super().__iter__()

    channel = CLIControlChannel(console=DummyConsole())
    request = _make_request()
    request.request_type = ControlRequestType.INPUTS
    request.items = SummaryEmptyItems(
        [
            ControlRequestItem(
                item_id="choices",
                label="Choices",
                request_type=ControlRequestType.SELECT,
                message="Choose items",
                options=[ControlOption(label="A", value="a"), ControlOption(label="B", value="b")],
                required=True,
            )
        ]
    )

    monkeypatch.setattr(channel, "_handle_options", lambda *_a, **_k: ["a", "b"])

    result = channel._handle_inputs(request)

    assert result["choices"] == ["a", "b"]
    assert any("choices" in msg for msg in channel.console.messages)


def test_prompt_for_input_unknown_type_falls_back(monkeypatch):
    channel = CLIControlChannel(console=DummyConsole())
    request = _make_request()
    request.request_type = ControlRequestType.SELECT

    monkeypatch.setattr("tactus.adapters.channels.cli.Prompt.ask", lambda *args, **kwargs: "value")

    assert channel._prompt_for_input(request) == "value"


def test_prompt_for_input_cancelled_returns_none():
    channel = CLIControlChannel(console=DummyConsole())
    channel._cancel_event.set()
    request = _make_request()

    assert channel._prompt_for_input(request) is None


def test_prompt_for_input_routes_to_handlers(monkeypatch):
    channel = CLIControlChannel(console=DummyConsole())

    monkeypatch.setattr(channel, "_handle_approval", lambda *_args: "approval")
    monkeypatch.setattr(channel, "_handle_input", lambda *_args: "input")
    monkeypatch.setattr(channel, "_handle_review", lambda *_args: "review")
    monkeypatch.setattr(channel, "_handle_escalation", lambda *_args: "escalation")
    monkeypatch.setattr(channel, "_handle_inputs", lambda *_args: "inputs")

    request = _make_request()
    request.request_type = ControlRequestType.APPROVAL
    assert channel._prompt_for_input(request) == "approval"

    request.request_type = ControlRequestType.INPUT
    assert channel._prompt_for_input(request) == "input"

    request.request_type = ControlRequestType.REVIEW
    assert channel._prompt_for_input(request) == "review"

    request.request_type = ControlRequestType.ESCALATION
    assert channel._prompt_for_input(request) == "escalation"

    request.request_type = ControlRequestType.INPUTS
    assert channel._prompt_for_input(request) == "inputs"


def test_handle_review_returns_none_if_cancelled_after_prompt(monkeypatch):
    channel = CLIControlChannel(console=DummyConsole())
    request = _make_request()

    states = iter([False, False, True])
    monkeypatch.setattr(channel, "is_cancelled", lambda: next(states))
    monkeypatch.setattr("tactus.adapters.channels.cli.Prompt.ask", lambda *args, **kwargs: "1")

    assert channel._handle_review(request) is None


def test_handle_approval_cancelled_after_confirm(monkeypatch):
    channel = CLIControlChannel(console=DummyConsole())
    request = _make_request()

    states = iter([False, True])
    monkeypatch.setattr(channel, "is_cancelled", lambda: next(states))
    monkeypatch.setattr("tactus.adapters.channels.cli.Confirm.ask", lambda *args, **kwargs: True)

    assert channel._handle_approval(request) is None


def test_handle_input_eof_returns_none(monkeypatch):
    channel = CLIControlChannel(console=DummyConsole())
    request = _make_request()

    def fake_prompt(*args, **kwargs):
        raise EOFError

    monkeypatch.setattr("tactus.adapters.channels.cli.Prompt.ask", fake_prompt)

    assert channel._handle_input(request) is None


def test_handle_options_cancelled_returns_none():
    channel = CLIControlChannel(console=DummyConsole())
    channel._cancel_event.set()
    options = [ControlOption(label="One", value="a")]

    assert channel._handle_options(options, None) is None


def test_handle_review_edit_cancelled_after_feedback(monkeypatch):
    channel = CLIControlChannel(console=DummyConsole())
    request = _make_request()

    answers = iter(["2", "edit feedback"])
    states = iter([False, False, True])

    monkeypatch.setattr(
        "tactus.adapters.channels.cli.Prompt.ask", lambda *args, **kwargs: next(answers)
    )
    monkeypatch.setattr(channel, "is_cancelled", lambda: next(states))

    assert channel._handle_review(request) is None


def test_handle_escalation_eof_returns_none(monkeypatch):
    channel = CLIControlChannel(console=DummyConsole())

    def fake_confirm(*args, **kwargs):
        raise EOFError

    monkeypatch.setattr("tactus.adapters.channels.cli.Confirm.ask", fake_confirm)

    assert channel._handle_escalation(_make_request()) is None


def test_show_cancelled_prints_reason():
    channel = CLIControlChannel(console=DummyConsole())
    channel._show_cancelled("Responded via other")

    assert any("Responded via other" in msg for msg in channel.console.messages)


def test_is_cli_available(monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    assert CLIControlChannel(console=DummyConsole())
    from tactus.adapters.channels.cli import is_cli_available

    assert is_cli_available() is False
