"""Tests for log handler adapters."""

from datetime import datetime
from types import SimpleNamespace

import requests

from tactus.adapters.cost_collector_log import CostCollectorLogHandler
from tactus.adapters.http_callback_log import HTTPCallbackLogHandler
from tactus.adapters.ide_log import IDELogHandler
from tactus.protocols.models import LogEvent, CostEvent, AgentStreamChunkEvent


def _cost_event():
    return CostEvent(
        agent_name="agent",
        model="gpt-4o",
        provider="openai",
        prompt_tokens=1,
        completion_tokens=1,
        total_tokens=2,
        prompt_cost=0.01,
        completion_cost=0.02,
        total_cost=0.03,
    )


def test_cost_collector_log_handler_tracks_cost_events():
    handler = CostCollectorLogHandler()
    handler.log(_cost_event())

    assert handler.cost_events


def test_cost_collector_log_handler_logs_levels(caplog):
    handler = CostCollectorLogHandler()
    event_logger = "test.logger"

    caplog.set_level("DEBUG")

    handler.log(LogEvent(level="DEBUG", message="debug", logger_name=event_logger))
    handler.log(LogEvent(level="WARNING", message="warn", logger_name=event_logger))
    handler.log(LogEvent(level="ERROR", message="err", logger_name=event_logger))
    handler.log(LogEvent(level="INFO", message="info", logger_name=event_logger))

    assert any("debug" in record.message for record in caplog.records)
    assert any("warn" in record.message for record in caplog.records)
    assert any("err" in record.message for record in caplog.records)
    assert any("info" in record.message for record in caplog.records)


def test_cost_collector_log_handler_logs_context(caplog):
    handler = CostCollectorLogHandler()
    event_logger = "test.logger"
    caplog.set_level("INFO")

    handler.log(
        LogEvent(
            level="INFO",
            message="context",
            context={"a": 1},
            logger_name=event_logger,
        )
    )

    assert any("Context" in record.message for record in caplog.records)


def test_cost_collector_log_handler_ignores_unknown_event():
    handler = CostCollectorLogHandler()
    handler.log(SimpleNamespace())


def test_http_callback_log_handler_posts_event(monkeypatch):
    handler = HTTPCallbackLogHandler("http://example.com")

    class FakeResponse:
        def raise_for_status(self):
            return None

    def fake_post(*args, **kwargs):
        return FakeResponse()

    handler.session.post = fake_post

    handler.log(LogEvent(level="INFO", message="hello"))
    handler.log(_cost_event())

    assert handler.cost_events


def test_http_callback_log_handler_handles_request_errors(monkeypatch):
    handler = HTTPCallbackLogHandler("http://example.com")

    def fake_post(*args, **kwargs):
        raise requests.RequestException("boom")

    handler.session.post = fake_post

    handler.log(LogEvent(level="INFO", message="hello"))


def test_http_callback_log_handler_handles_unexpected_errors(monkeypatch):
    handler = HTTPCallbackLogHandler("http://example.com")
    captured = {}

    def fake_post(*args, **kwargs):
        captured.update(kwargs.get("json", {}))
        raise ValueError("boom")

    handler.session.post = fake_post

    handler.log(LogEvent(level="INFO", message="hello", timestamp=datetime(2024, 1, 1)))

    assert captured["timestamp"].endswith("Z")


def test_http_callback_log_handler_from_environment(monkeypatch):
    monkeypatch.setenv("TACTUS_CALLBACK_URL", "http://example.com")
    handler = HTTPCallbackLogHandler.from_environment()

    assert isinstance(handler, HTTPCallbackLogHandler)


def test_http_callback_log_handler_from_environment_missing(monkeypatch):
    monkeypatch.delenv("TACTUS_CALLBACK_URL", raising=False)
    assert HTTPCallbackLogHandler.from_environment() is None


def test_ide_log_handler_collects_events():
    handler = IDELogHandler()

    log_event = LogEvent(level="INFO", message="hello")
    stream_event = AgentStreamChunkEvent(
        agent_name="agent",
        chunk_text="hi",
        accumulated_text="hi",
    )
    handler.log(log_event)
    handler.log(stream_event)
    handler.log(_cost_event())

    events = handler.get_events()

    assert log_event in events
    assert stream_event in events
    assert handler.cost_events
