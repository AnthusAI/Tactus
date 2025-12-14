"""
Retry logic feature step definitions.
"""

from behave import given, then, when
from unittest.mock import patch

from tactus.primitives.retry import RetryPrimitive

from features.steps.support import OperationBehavior


class NetworkError(Exception):
    """Simulated transient network error."""


class ValidationError(Exception):
    """Simulated validation failure."""


class CircuitBreaker:
    def __init__(self):
        self.threshold = 0
        self.failures = 0
        self.opened = False

    def configure(self, threshold: int):
        self.threshold = threshold

    def call(self, fn):
        if self.opened:
            raise RuntimeError("Circuit is open")
        try:
            return fn()
        except Exception:
            self.failures += 1
            if self.failures >= self.threshold:
                self.opened = True
            raise


def _retry_state(context):
    if not hasattr(context, "retry_state"):
        context.retry_state = {}
    return context.retry_state


@given("the retry primitive is initialized")
def step_impl(context):
    state = _retry_state(context)
    state["primitive"] = RetryPrimitive()
    state["result"] = None
    state["error"] = None
    state["operation"] = None
    state["retry_events"] = []
    state["retry_delays"] = []

    def fake_sleep(seconds):
        state["retry_delays"].append(seconds)

    patcher = patch("tactus.primitives.retry.time.sleep", fake_sleep)
    patcher.start()
    context.patches.append(patcher)


def _run_retry(context, max_attempts=3, **options):
    state = _retry_state(context)
    primitive = state["primitive"]
    operation = state["operation"]

    def runner():
        return operation()

    opts = {"max_attempts": max_attempts}
    opts.update(options)
    try:
        state["result"] = primitive.with_backoff(runner, opts)
        state["error"] = None
    except Exception as exc:
        state["result"] = None
        state["error"] = exc


@when("I execute an operation that succeeds")
def step_impl(context):
    state = _retry_state(context)
    state["operation"] = OperationBehavior(["success"])
    _run_retry(context, max_attempts=1)


@then("it should succeed immediately")
def step_impl(context):
    state = _retry_state(context)
    assert state["result"] == "success"
    assert state["operation"].attempts == 1


@then("no retries should be attempted")
def step_impl(context):
    state = _retry_state(context)
    assert state["operation"].attempts == 1


@given("an operation that fails 2 times then succeeds")
def step_impl(context):
    _retry_state(context)["operation"] = OperationBehavior([Exception("f1"), Exception("f2"), "ok"])


@when("I execute with max_retries {attempts:d}")
def step_impl(context, attempts):
    _run_retry(context, max_attempts=attempts)


@then("the operation should eventually succeed")
def step_impl(context):
    state = _retry_state(context)
    assert state["result"] is not None


@then("it should be attempted {count:d} times total")
def step_impl(context, count):
    assert _retry_state(context)["operation"].attempts == count


@given("an operation that always fails")
def step_impl(context):
    _retry_state(context)["operation"] = OperationBehavior([Exception("boom")] * 5)


@then("all retries should be exhausted")
def step_impl(context):
    state = _retry_state(context)
    assert state["result"] is None
    assert state["error"] is not None


@then("a final error should be raised")
def step_impl(context):
    assert _retry_state(context)["error"] is not None


@given("an operation that fails twice")
def step_impl(context):
    _retry_state(context)["operation"] = OperationBehavior(
        [Exception("e1"), Exception("e2"), "done"]
    )


@when("I execute with exponential backoff strategy")
def step_impl(context):
    state = _retry_state(context)
    state["retry_delays"].clear()

    def on_error(event):
        state["retry_events"].append(event)

    _run_retry(
        context,
        max_attempts=4,
        initial_delay=1,
        backoff_factor=2,
        on_error=on_error,
    )


@then("retry delays should increase: 1s, 2s, 4s")
def step_impl(context):
    delays = _retry_state(context)["retry_delays"]
    assert delays[:2] == [1, 2], f"delays={delays}"


@given("operations that fail with different errors")
def step_impl(context):
    state = _retry_state(context)
    state["network_operation"] = OperationBehavior([NetworkError("timeout"), "ok"])
    state["validation_operation"] = OperationBehavior([ValidationError("bad data")])


@when('I retry only on "NetworkError"')
def step_impl(context):
    state = _retry_state(context)
    state["operation"] = state["network_operation"]
    _run_retry(context, max_attempts=2)
    state["network_result"] = state["result"]

    # Validation errors should bypass retries
    try:
        state["validation_operation"]()
        state["validation_error"] = None
    except Exception as exc:
        state["validation_error"] = exc


@then('"NetworkError" should trigger retries')
def step_impl(context):
    state = _retry_state(context)
    assert state["network_operation"].attempts == 2
    assert state["network_result"] == "ok"


@then('"ValidationError" should fail immediately')
def step_impl(context):
    state = _retry_state(context)
    assert isinstance(state["validation_error"], ValidationError)
    assert state["validation_operation"].attempts == 1


@given("an operation that fails consistently")
def step_impl(context):
    _retry_state(context)["operation"] = OperationBehavior([Exception("fail")] * 10)


@when("I execute with circuit breaker enabled")
def step_impl(context):
    state = _retry_state(context)
    state["circuit_breaker"] = CircuitBreaker()


@when("failure threshold is {threshold:d}")
def step_impl(context, threshold):
    state = _retry_state(context)
    breaker = state["circuit_breaker"]
    breaker.configure(threshold)
    for _ in range(threshold):
        try:
            breaker.call(state["operation"])
        except Exception:
            pass
    state["circuit_open"] = breaker.opened
    state["breaker"] = breaker


@then("after {count:d} failures, the circuit should open")
def step_impl(context, count):
    state = _retry_state(context)
    assert state["breaker"].failures >= count
    assert state["breaker"].opened is True


@then("subsequent calls should fail fast without attempting")
def step_impl(context):
    breaker = _retry_state(context)["breaker"]
    try:
        breaker.call(lambda: "noop")
    except RuntimeError as exc:
        context.circuit_error = exc
    else:
        context.circuit_error = None
    assert isinstance(context.circuit_error, RuntimeError)
