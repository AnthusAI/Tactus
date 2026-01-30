"""Tests for IDE logging capture."""

import logging
import queue
import sys
from pathlib import Path

backend_path = Path(__file__).resolve().parents[2] / "tactus-ide" / "backend"
sys.path.insert(0, str(backend_path))

from logging_capture import CaptureHandler, EventCollector  # noqa: E402


def test_capture_handler_extracts_context_and_cleans_message():
    event_queue = queue.Queue()
    handler = CaptureHandler(event_queue, procedure_id="proc-1")
    handler.setFormatter(logging.Formatter("%(message)s"))

    record = logging.LogRecord(
        name="tactus",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg='Processing item\nContext: {"foo": "bar"}',
        args=(),
        exc_info=None,
    )

    handler.emit(record)
    event = event_queue.get_nowait()

    assert event.message == "Processing item"
    assert event.context == {"foo": "bar"}
    assert event.level == "INFO"
    assert event.logger_name == "tactus"
    assert event.procedure_id == "proc-1"


def test_capture_handler_ignores_invalid_context():
    event_queue = queue.Queue()
    handler = CaptureHandler(event_queue)
    handler.setFormatter(logging.Formatter("%(message)s"))

    record = logging.LogRecord(
        name="tactus",
        level=logging.WARNING,
        pathname=__file__,
        lineno=20,
        msg="Bad context\nContext: {oops}",
        args=(),
        exc_info=None,
    )

    handler.emit(record)
    event = event_queue.get_nowait()

    assert event.message == "Bad context\nContext: {oops}"
    assert event.context is None


def test_event_collector_captures_logger_events():
    logger_name = "tactus.capture.test"
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)

    collector = EventCollector(procedure_id="proc-2", logger_name=logger_name)
    with collector:
        logger.info("hello")

    events = collector.get_events()

    assert events
    assert events[0].message == "hello"
    assert events[0].procedure_id == "proc-2"


def test_capture_handler_emit_handles_exception(capsys):
    event_queue = queue.Queue()
    handler = CaptureHandler(event_queue)

    def boom(_record):
        raise RuntimeError("format failed")

    handler.format = boom

    record = logging.LogRecord(
        name="tactus",
        level=logging.ERROR,
        pathname=__file__,
        lineno=30,
        msg="ignored",
        args=(),
        exc_info=None,
    )

    handler.emit(record)
    output = capsys.readouterr().out

    assert "Error in CaptureHandler: format failed" in output


def test_event_collector_start_idempotent():
    logger_name = "tactus.capture.idempotent"
    logger = logging.getLogger(logger_name)
    logger.handlers.clear()

    collector = EventCollector(logger_name=logger_name)
    collector.start()
    collector.start()

    assert len(logger.handlers) == 1
    collector.stop()


def test_event_collector_stop_without_start():
    collector = EventCollector()

    collector.stop()

    assert collector.handler is None
    assert collector.logger is None
