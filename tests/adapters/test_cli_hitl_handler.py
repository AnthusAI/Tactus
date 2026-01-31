import io
from datetime import datetime

from rich.console import Console

from tactus.adapters.cli_hitl import CLIHITLHandler
from tactus.protocols.models import HITLRequest


def test_request_interaction_routes_to_approval(monkeypatch):
    console = Console(file=io.StringIO(), force_terminal=False)
    handler = CLIHITLHandler(console=console)

    monkeypatch.setattr("tactus.adapters.cli_hitl.Confirm.ask", lambda *_a, **_k: True)

    request = HITLRequest(request_type="approval", message="Approve?", default_value=False)
    response = handler.request_interaction("proc", request)

    assert response.value is True
    assert response.timed_out is False
    assert isinstance(response.responded_at, datetime)


def test_request_interaction_routes_to_input_with_options(monkeypatch):
    console = Console(file=io.StringIO(), force_terminal=False)
    handler = CLIHITLHandler(console=console)

    prompt_values = iter(["2"])

    monkeypatch.setattr(
        "tactus.adapters.cli_hitl.Prompt.ask", lambda *_a, **_k: next(prompt_values)
    )

    request = HITLRequest(
        request_type="input",
        message="Pick one",
        options=[
            {"label": "First", "value": "a", "description": "Desc"},
            {"label": "Second", "value": "b"},
        ],
    )
    response = handler.request_interaction("proc", request)

    assert response.value == "b"


def test_request_interaction_routes_to_review(monkeypatch):
    console = Console(file=io.StringIO(), force_terminal=False)
    handler = CLIHITLHandler(console=console)

    prompt_values = iter(["reject", "Needs changes"])

    monkeypatch.setattr(
        "tactus.adapters.cli_hitl.Prompt.ask", lambda *_a, **_k: next(prompt_values)
    )

    request = HITLRequest(request_type="review", message="Review this")
    response = handler.request_interaction("proc", request)

    assert response.value["decision"] == "rejected"
    assert response.value["feedback"] == "Needs changes"


def test_request_interaction_review_invalid_choice_then_approve(monkeypatch):
    console = Console(file=io.StringIO(), force_terminal=False)
    handler = CLIHITLHandler(console=console)

    answers = iter(["invalid", "approve"])
    monkeypatch.setattr("tactus.adapters.cli_hitl.Prompt.ask", lambda *_a, **_k: next(answers))

    request = HITLRequest(request_type="review", message="Review this")
    response = handler.request_interaction("proc", request)

    assert response.value["decision"] == "approved"


def test_request_interaction_routes_to_escalation(monkeypatch):
    console = Console(file=io.StringIO(), force_terminal=False)
    handler = CLIHITLHandler(console=console)

    monkeypatch.setattr("tactus.adapters.cli_hitl.Confirm.ask", lambda *_a, **_k: True)

    request = HITLRequest(request_type="escalation", message="Escalate")
    response = handler.request_interaction("proc", request)

    assert response.value is None


def test_request_interaction_unknown_type_defaults_to_input(monkeypatch):
    console = Console(file=io.StringIO(), force_terminal=False)
    handler = CLIHITLHandler(console=console)

    monkeypatch.setattr("tactus.adapters.cli_hitl.Prompt.ask", lambda *_a, **_k: "value")

    request = HITLRequest(request_type="custom", message="Enter value")
    response = handler.request_interaction("proc", request)

    assert response.value == "value"


def test_handle_inputs_collects_values(monkeypatch):
    console = Console(file=io.StringIO(), force_terminal=False)
    handler = CLIHITLHandler(console=console)

    prompt_values = iter(
        [
            "1,2",  # select multiple
            "approve",  # review choice
        ]
    )

    monkeypatch.setattr(
        "tactus.adapters.cli_hitl.Prompt.ask", lambda *_a, **_k: next(prompt_values)
    )
    monkeypatch.setattr("tactus.adapters.cli_hitl.Confirm.ask", lambda *_a, **_k: True)

    request = HITLRequest(
        request_type="inputs",
        message="Batch",
        metadata={
            "items": [
                {"item_id": "approved", "label": "Approve", "request_type": "approval"},
                {
                    "item_id": "choices",
                    "label": "Pick",
                    "request_type": "select",
                    "options": [{"label": "A", "value": "a"}, {"label": "B", "value": "b"}],
                    "metadata": {"mode": "multiple", "min": 1, "max": 2},
                },
                {"item_id": "review", "label": "Review", "request_type": "review"},
            ]
        },
    )

    response = handler.request_interaction("proc", request)

    assert response.value == {
        "approved": True,
        "choices": ["a", "b"],
        "review": {"decision": "approved", "feedback": None},
    }


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

    console = Console(file=io.StringIO(), force_terminal=False)
    handler = CLIHITLHandler(console=console)

    monkeypatch.setattr("tactus.adapters.cli_hitl.Prompt.ask", lambda *_a, **_k: "1,2")

    items = SummaryEmptyItems(
        [
            {
                "item_id": "choices",
                "label": "Choices",
                "request_type": "select",
                "options": [{"label": "A", "value": "a"}, {"label": "B", "value": "b"}],
                "metadata": {"mode": "multiple"},
            }
        ]
    )

    request = HITLRequest(
        request_type="inputs",
        message="Batch",
        metadata={"items": items},
    )
    response = handler.request_interaction("proc", request)

    assert response.value["choices"] == ["a", "b"]
    assert "choices" in console.file.getvalue()


def test_handle_inputs_missing_items_returns_empty():
    console = Console(file=io.StringIO(), force_terminal=False)
    handler = CLIHITLHandler(console=console)

    request = HITLRequest(request_type="inputs", message="Batch", metadata={})
    response = handler.request_interaction("proc", request)

    assert response.value == {}


def test_request_interaction_routes_to_input_freeform(monkeypatch):
    console = Console(file=io.StringIO(), force_terminal=False)
    handler = CLIHITLHandler(console=console)

    monkeypatch.setattr("tactus.adapters.cli_hitl.Prompt.ask", lambda *_a, **_k: "value")

    request = HITLRequest(request_type="input", message="Enter value")
    response = handler.request_interaction("proc", request)

    assert response.value == "value"


def test_input_options_invalid_then_valid(monkeypatch):
    console = Console(file=io.StringIO(), force_terminal=False)
    handler = CLIHITLHandler(console=console)

    answers = iter(["bad", "3", "1"])
    monkeypatch.setattr("tactus.adapters.cli_hitl.Prompt.ask", lambda *_a, **_k: next(answers))

    request = HITLRequest(
        request_type="input",
        message="Pick one",
        options=[{"label": "First", "value": "a"}, {"label": "Second", "value": "b"}],
    )
    response = handler.request_interaction("proc", request)

    assert response.value == "a"


def test_request_interaction_routes_to_review_edit(monkeypatch):
    console = Console(file=io.StringIO(), force_terminal=False)
    handler = CLIHITLHandler(console=console)

    answers = iter(["edit", "Please change"])
    monkeypatch.setattr("tactus.adapters.cli_hitl.Prompt.ask", lambda *_a, **_k: next(answers))

    request = HITLRequest(request_type="review", message="Review this")
    response = handler.request_interaction("proc", request)

    assert response.value["decision"] == "approved"
    assert response.value["feedback"] == "Please change"


def test_request_interaction_routes_to_review_approve(monkeypatch):
    console = Console(file=io.StringIO(), force_terminal=False)
    handler = CLIHITLHandler(console=console)

    monkeypatch.setattr("tactus.adapters.cli_hitl.Prompt.ask", lambda *_a, **_k: "approve")

    request = HITLRequest(request_type="review", message="Review this")
    response = handler.request_interaction("proc", request)

    assert response.value["decision"] == "approved"
    assert response.value["feedback"] is None


def test_handle_inputs_select_single(monkeypatch):
    console = Console(file=io.StringIO(), force_terminal=False)
    handler = CLIHITLHandler(console=console)

    answers = iter(["2"])
    monkeypatch.setattr("tactus.adapters.cli_hitl.Prompt.ask", lambda *_a, **_k: next(answers))

    request = HITLRequest(
        request_type="inputs",
        message="Batch",
        metadata={
            "items": [
                {
                    "item_id": "choice",
                    "label": "Pick",
                    "request_type": "select",
                    "options": ["a", "b"],
                }
            ]
        },
    )

    response = handler.request_interaction("proc", request)
    assert response.value["choice"] == "b"


def test_handle_inputs_select_single_with_description_and_invalid(monkeypatch):
    console = Console(file=io.StringIO(), force_terminal=False)
    handler = CLIHITLHandler(console=console)

    answers = iter(["bad", "3", "1"])
    monkeypatch.setattr("tactus.adapters.cli_hitl.Prompt.ask", lambda *_a, **_k: next(answers))

    request = HITLRequest(
        request_type="inputs",
        message="Batch",
        metadata={
            "items": [
                {
                    "item_id": "choice",
                    "label": "Pick",
                    "request_type": "select",
                    "options": [
                        {"label": "Alpha", "value": "a", "description": "Desc"},
                        {"label": "Beta", "value": "b"},
                    ],
                }
            ]
        },
    )

    response = handler.request_interaction("proc", request)
    assert response.value["choice"] == "a"


def test_handle_inputs_select_multiple_validation(monkeypatch):
    console = Console(file=io.StringIO(), force_terminal=False)
    handler = CLIHITLHandler(console=console)

    answers = iter(["1", "1,2,3", "1,2"])
    monkeypatch.setattr("tactus.adapters.cli_hitl.Prompt.ask", lambda *_a, **_k: next(answers))

    request = HITLRequest(
        request_type="inputs",
        message="Batch",
        metadata={
            "items": [
                {
                    "item_id": "choices",
                    "label": "Pick",
                    "request_type": "select",
                    "options": ["a", "b", "c"],
                    "metadata": {"mode": "multiple", "min": 2, "max": 2},
                }
            ]
        },
    )

    response = handler.request_interaction("proc", request)
    assert response.value["choices"] == ["a", "b"]


def test_handle_inputs_select_multiple_invalid_range(monkeypatch):
    console = Console(file=io.StringIO(), force_terminal=False)
    handler = CLIHITLHandler(console=console)

    answers = iter(["3", "1"])
    monkeypatch.setattr("tactus.adapters.cli_hitl.Prompt.ask", lambda *_a, **_k: next(answers))

    request = HITLRequest(
        request_type="inputs",
        message="Batch",
        metadata={
            "items": [
                {
                    "item_id": "choices",
                    "label": "Pick",
                    "request_type": "select",
                    "options": ["a", "b"],
                    "metadata": {"mode": "multiple", "min": 1, "max": 2},
                }
            ]
        },
    )

    response = handler.request_interaction("proc", request)
    assert response.value["choices"] == ["a"]


def test_handle_inputs_select_multiple_invalid_input(monkeypatch):
    console = Console(file=io.StringIO(), force_terminal=False)
    handler = CLIHITLHandler(console=console)

    answers = iter(["bad", "1,2"])
    monkeypatch.setattr("tactus.adapters.cli_hitl.Prompt.ask", lambda *_a, **_k: next(answers))

    request = HITLRequest(
        request_type="inputs",
        message="Batch",
        metadata={
            "items": [
                {
                    "item_id": "choices",
                    "label": "Pick",
                    "request_type": "select",
                    "options": ["a", "b"],
                    "metadata": {"mode": "multiple", "min": 1, "max": 2},
                }
            ]
        },
    )

    response = handler.request_interaction("proc", request)
    assert response.value["choices"] == ["a", "b"]


def test_handle_inputs_review_reject(monkeypatch):
    console = Console(file=io.StringIO(), force_terminal=False)
    handler = CLIHITLHandler(console=console)

    answers = iter(["reject", "Needs changes"])
    monkeypatch.setattr("tactus.adapters.cli_hitl.Prompt.ask", lambda *_a, **_k: next(answers))

    request = HITLRequest(
        request_type="inputs",
        message="Batch",
        metadata={"items": [{"item_id": "review", "label": "Review", "request_type": "review"}]},
    )

    response = handler.request_interaction("proc", request)
    assert response.value["review"]["decision"] == "rejected"
    assert response.value["review"]["feedback"] == "Needs changes"


def test_handle_inputs_review_invalid_choice_then_approve(monkeypatch):
    console = Console(file=io.StringIO(), force_terminal=False)
    handler = CLIHITLHandler(console=console)

    answers = iter(["invalid", "approve"])
    monkeypatch.setattr("tactus.adapters.cli_hitl.Prompt.ask", lambda *_a, **_k: next(answers))

    request = HITLRequest(
        request_type="inputs",
        message="Batch",
        metadata={"items": [{"item_id": "review", "label": "Review", "request_type": "review"}]},
    )

    response = handler.request_interaction("proc", request)
    assert response.value["review"]["decision"] == "approved"


def test_handle_inputs_default_multiline(monkeypatch):
    console = Console(file=io.StringIO(), force_terminal=False)
    handler = CLIHITLHandler(console=console)

    answers = iter(["line1", "line2", None])

    def fake_prompt(*_a, **_k):
        value = next(answers)
        if value is None:
            raise EOFError
        return value

    monkeypatch.setattr("tactus.adapters.cli_hitl.Prompt.ask", fake_prompt)

    request = HITLRequest(
        request_type="inputs",
        message="Batch",
        metadata={
            "items": [
                {
                    "item_id": "notes",
                    "label": "Notes",
                    "request_type": "input",
                    "metadata": {"multiline": True},
                }
            ]
        },
    )

    response = handler.request_interaction("proc", request)
    assert response.value["notes"] == "line1\nline2"


def test_handle_inputs_default_single_line_with_placeholder(monkeypatch):
    console = Console(file=io.StringIO(), force_terminal=False)
    handler = CLIHITLHandler(console=console)

    monkeypatch.setattr("tactus.adapters.cli_hitl.Prompt.ask", lambda *_a, **_k: "ok")

    request = HITLRequest(
        request_type="inputs",
        message="Batch",
        metadata={
            "items": [
                {
                    "item_id": "note",
                    "label": "Note",
                    "request_type": "input",
                    "metadata": {"placeholder": "hint"},
                }
            ]
        },
    )

    response = handler.request_interaction("proc", request)
    assert response.value["note"] == "ok"


def test_handle_inputs_skips_optional_empty_value(monkeypatch):
    console = Console(file=io.StringIO(), force_terminal=False)
    handler = CLIHITLHandler(console=console)

    monkeypatch.setattr("tactus.adapters.cli_hitl.Prompt.ask", lambda *_a, **_k: "")

    request = HITLRequest(
        request_type="inputs",
        message="Batch",
        metadata={
            "items": [
                {
                    "item_id": "optional",
                    "label": "Optional",
                    "request_type": "input",
                    "required": False,
                }
            ]
        },
    )

    response = handler.request_interaction("proc", request)
    assert "optional" not in response.value


def test_handle_inputs_review_edit(monkeypatch):
    console = Console(file=io.StringIO(), force_terminal=False)
    handler = CLIHITLHandler(console=console)

    answers = iter(["edit", "Please change"])
    monkeypatch.setattr("tactus.adapters.cli_hitl.Prompt.ask", lambda *_a, **_k: next(answers))

    request = HITLRequest(
        request_type="inputs",
        message="Batch",
        metadata={
            "items": [
                {"item_id": "review", "label": "Review", "request_type": "review"},
            ]
        },
    )

    response = handler.request_interaction("proc", request)
    assert response.value["review"]["decision"] == "approved"
    assert response.value["review"]["feedback"] == "Please change"


def test_handle_inputs_summary_truncates_long_values(monkeypatch):
    output = io.StringIO()
    console = Console(file=output, force_terminal=False)
    handler = CLIHITLHandler(console=console)

    monkeypatch.setattr("tactus.adapters.cli_hitl.Prompt.ask", lambda *_a, **_k: "x" * 80)

    request = HITLRequest(
        request_type="inputs",
        message="Batch",
        metadata={
            "items": [
                {"item_id": "note", "label": "Note", "request_type": "input"},
            ]
        },
    )

    handler.request_interaction("proc", request)
    assert "..." in output.getvalue()


def test_check_pending_response_and_cancel_noops():
    console = Console(file=io.StringIO(), force_terminal=False)
    handler = CLIHITLHandler(console=console)

    assert handler.check_pending_response("proc", "msg") is None
    handler.cancel_pending_request("proc", "msg")


def test_check_pending_response_returns_none():
    console = Console(file=io.StringIO(), force_terminal=False)
    handler = CLIHITLHandler(console=console)

    assert handler.check_pending_response("proc", "msg") is None
