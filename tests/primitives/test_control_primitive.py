import logging

from tactus.primitives.control import IterationsPrimitive, StopPrimitive


def test_iterations_primitive():
    iterations = IterationsPrimitive()
    assert iterations.current() == 0
    assert iterations.increment() == 1
    assert iterations.exceeded(1) is True
    iterations.reset()
    assert iterations.current() == 0
    assert "IterationsPrimitive" in repr(iterations)


def test_iterations_exceeded_logs_warning(caplog):
    iterations = IterationsPrimitive()
    iterations.increment()

    caplog.set_level(logging.WARNING)
    assert iterations.exceeded(1) is True
    assert any("Iterations exceeded" in record.message for record in caplog.records)


def test_iterations_exceeded_false_does_not_warn(caplog):
    iterations = IterationsPrimitive()
    caplog.set_level(logging.WARNING, logger="tactus.primitives.control")

    assert iterations.exceeded(1) is False
    assert not any("Iterations exceeded" in record.message for record in caplog.records)


def test_stop_primitive():
    stop = StopPrimitive()
    assert stop.requested() is False
    assert stop.reason() is None
    assert stop.success() is True

    stop.request("done", success=False)
    assert stop.requested() is True
    assert stop.reason() == "done"
    assert stop.success() is False

    stop.reset()
    assert stop.requested() is False
    assert "StopPrimitive" in repr(stop)


def test_stop_request_logs_info(caplog):
    stop = StopPrimitive()
    caplog.set_level(logging.INFO, logger="tactus.primitives.control")
    stop.request("done", success=True)
    assert any("Stop requested" in record.message for record in caplog.records)
