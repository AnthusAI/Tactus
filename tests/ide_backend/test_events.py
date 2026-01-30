"""Tests for IDE event models."""

from datetime import datetime
import sys
from pathlib import Path

backend_path = Path(__file__).resolve().parents[2] / "tactus-ide" / "backend"
sys.path.insert(0, str(backend_path))

from events import (  # noqa: E402
    LogEvent,
    ExecutionEvent,
    OutputEvent,
    ValidationEvent,
    LoadingEvent,
)


def test_log_event_defaults():
    event = LogEvent(level="INFO", message="hello")
    assert event.event_type == "log"
    assert event.level == "INFO"
    assert event.message == "hello"
    assert isinstance(event.timestamp, datetime)


def test_execution_event_fields():
    event = ExecutionEvent(lifecycle_stage="start", details={"step": 1})
    assert event.event_type == "execution"
    assert event.lifecycle_stage == "start"
    assert event.details == {"step": 1}


def test_output_event_fields():
    event = OutputEvent(stream="stdout", content="line")
    assert event.event_type == "output"
    assert event.stream == "stdout"
    assert event.content == "line"


def test_validation_event_defaults():
    event = ValidationEvent(valid=False)
    assert event.event_type == "validation"
    assert event.valid is False
    assert event.errors == []


def test_loading_event_fields():
    event = LoadingEvent(message="loading")
    assert event.event_type == "loading"
    assert event.message == "loading"
