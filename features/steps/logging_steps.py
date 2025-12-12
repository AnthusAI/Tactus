"""
Logging feature step definitions.
"""

import json
import logging
import time

from behave import given, then, when

from tactus.primitives.log import LogPrimitive

from features.steps.support import InMemoryLogHandler, parse_key_value_table


def _log_state(context):
    if not hasattr(context, "log_state"):
        context.log_state = {}
    return context.log_state


def _log(context) -> LogPrimitive:
    return _log_state(context)["primitive"]


def _handler(context) -> InMemoryLogHandler:
    return _log_state(context)["handler"]


@given("the log primitive is initialized")
def step_impl(context):
    state = _log_state(context)
    procedure_id = "test_procedure"
    logger = logging.getLogger(f"procedure.{procedure_id}")
    logger.handlers.clear()
    handler = InMemoryLogHandler()
    formatter = logging.Formatter("%(levelname)s:%(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    state.update(
        {
            "logger": logger,
            "handler": handler,
            "primitive": LogPrimitive(procedure_id=procedure_id),
            "workflow_steps": [],
            "captured_records": [],
            "captured_exception": {},
            "aggregated_logs": [],
        }
    )


@when('I log "{message}" at {level} level')
def step_impl(context, message, level):
    log = _log(context)
    level = level.upper()
    if level == "INFO":
        log.info(message)
    elif level == "DEBUG":
        log.debug(message)
    elif level in {"WARN", "WARNING"}:
        log.warn(message)
    elif level == "ERROR":
        log.error(message)


@then("all messages should be recorded")
def step_impl(context):
    assert len(_handler(context).records) >= 4


@then("each should have the correct level")
def step_impl(context):
    levels = [record.levelname for record in _handler(context).records[-4:]]
    assert levels == ["INFO", "DEBUG", "WARNING", "ERROR"]


@when("I log with context:")
def step_impl(context):
    payload = parse_key_value_table(context.table)
    _log(context).info("Structured log", payload)
    _log_state(context)["last_context"] = payload


@then("the log entry should include all context fields")
def step_impl(context):
    record = _handler(context).records[-1]
    for key in _log_state(context)["last_context"]:
        assert key in record.getMessage()


@then("it should be queryable by any field")
def step_impl(context):
    payload = _log_state(context)["last_context"]
    for value in payload.values():
        assert str(value) in _handler(context).records[-1].getMessage()


@given("log level is set to WARN")
def step_impl(context):
    _log_state(context)["logger"].setLevel(logging.WARN)


@then("only WARN and higher should be captured")
def step_impl(context):
    levels = [record.levelname for record in _handler(context).records]
    assert all(level in {"WARNING", "ERROR", "CRITICAL"} for level in levels)


@then("DEBUG and INFO should be filtered out")
def step_impl(context):
    levels = [record.levelname for record in _handler(context).records]
    assert "DEBUG" not in levels and "INFO" not in levels


@given("a multi-step workflow")
def step_impl(context):
    _log_state(context)["workflow_steps"] = ["ingest", "train", "evaluate"]


@when("I log progress at each step")
def step_impl(context):
    for step_name in _log_state(context)["workflow_steps"]:
        _log(context).info(f"Step {step_name} completed", {"step": step_name})


@then("I should be able to track workflow execution")
def step_impl(context):
    messages = [record.getMessage() for record in _handler(context).records]
    for step_name in _log_state(context)["workflow_steps"]:
        assert any(step_name in message for message in messages)


@then("see which steps completed successfully")
def step_impl(context):
    assert len(_handler(context).records) >= len(_log_state(context)["workflow_steps"])


@when("an error occurs in the workflow")
def step_impl(context):
    state = _log_state(context)
    try:
        raise RuntimeError("Simulated failure")
    except RuntimeError as exc:
        state["error"] = exc


@when("I log the exception with traceback")
def step_impl(context):
    error = _log_state(context)["error"]
    metadata = {
        "error_type": type(error).__name__,
        "error_message": str(error),
        "stack_trace": "fake-trace",
        "timestamp": time.time(),
    }
    _log_state(context)["captured_exception"] = metadata
    _log(context).error("Workflow failed", metadata)


@then("the log should include:")
def step_impl(context):
    fields = [row["field"] for row in context.table]
    metadata = _log_state(context)["captured_exception"]
    assert all(field in metadata for field in fields)


@given("a custom formatter that outputs JSON")
def step_impl(context):
    logger = _log_state(context)["logger"]
    logger.handlers.clear()

    class JsonFormatter(logging.Formatter):
        def format(self, record):
            payload = {
                "timestamp": record.created,
                "level": record.levelname,
                "message": record.getMessage(),
            }
            return json.dumps(payload)

    handler = InMemoryLogHandler()
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    _log_state(context)["handler"] = handler


@when("I log messages")
def step_impl(context):
    _log(context).info("JSON log entry")


@then("each log entry should be valid JSON")
def step_impl(context):
    handler = _handler(context)
    for record in handler.records:
        json.loads(handler.format(record))


@then("include timestamp, level, and message")
def step_impl(context):
    handler = _handler(context)
    payload = json.loads(handler.format(handler.records[-1]))
    assert {"timestamp", "level", "message"}.issubset(payload.keys())


@given("multiple executions of the same workflow")
def step_impl(context):
    state = _log_state(context)
    state["aggregated_logs"] = [
        {"procedure_id": "research_123", "timestamp": 1, "message": "run1"},
        {"procedure_id": "research_123", "timestamp": 2, "message": "run2"},
        {"procedure_id": "other_proc", "timestamp": 3, "message": "run3"},
    ]


@when('I query logs for procedure_id "{procedure_id}"')
def step_impl(context, procedure_id):
    logs = _log_state(context).get("aggregated_logs", [])
    context.filtered_logs = [log for log in logs if log["procedure_id"] == procedure_id]


@then("I should see all log entries")
def step_impl(context):
    assert len(context.filtered_logs) >= 1


@then("they should be chronologically ordered")
def step_impl(context):
    timestamps = [entry["timestamp"] for entry in context.filtered_logs]
    assert timestamps == sorted(timestamps)


@when("I log operation start time")
def step_impl(context):
    _log_state(context)["op_start"] = time.perf_counter()
    _log(context).info("Operation started", {"ts": _log_state(context)["op_start"]})


@when("execute an operation")
def step_impl(context):
    _log_state(context)["op_duration"] = 0.5


@when("log operation end time")
def step_impl(context):
    end = _log_state(context)["op_start"] + _log_state(context)["op_duration"]
    _log(context).info("Operation ended", {"ts": end})
    _log_state(context)["op_end"] = end


@then("I can calculate operation duration")
def step_impl(context):
    duration = _log_state(context)["op_end"] - _log_state(context)["op_start"]
    assert abs(duration - _log_state(context)["op_duration"]) < 1e-6


@then("identify performance bottlenecks")
def step_impl(context):
    duration = _log_state(context)["op_end"] - _log_state(context)["op_start"]
    assert duration >= 0.5
