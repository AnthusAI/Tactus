from pydantic import BaseModel

from tactus.sandbox import protocol
from tactus.sandbox.protocol import ExecutionRequest, ExecutionResult, ExecutionStatus


class DummyModel(BaseModel):
    value: int


def test_execution_request_json_round_trip():
    req = ExecutionRequest(source="print('hi')", params={"x": 1}, execution_id="1")
    encoded = req.to_json()
    decoded = ExecutionRequest.from_json(encoded)

    assert decoded.source == "print('hi')"
    assert decoded.params == {"x": 1}
    assert decoded.execution_id == "1"


def test_execution_result_success_failure_timeout():
    success = ExecutionResult.success(result={"ok": True}, duration_seconds=1.2)
    assert success.status == ExecutionStatus.SUCCESS

    failure = ExecutionResult.failure(error="boom", error_type="RuntimeError")
    assert failure.status == ExecutionStatus.ERROR
    assert failure.exit_code == 1

    timeout = ExecutionResult.timeout(duration_seconds=5.0)
    assert timeout.status == ExecutionStatus.TIMEOUT
    assert timeout.exit_code == 124


def test_execution_result_json_round_trip_with_enum():
    result = ExecutionResult(status=ExecutionStatus.SUCCESS, result={"ok": True})
    encoded = result.to_json()
    decoded = ExecutionResult.from_json(encoded)

    assert decoded.status == ExecutionStatus.SUCCESS
    assert decoded.result == {"ok": True}


def test_json_serializer_handles_models_and_dicts():
    model = DummyModel(value=3)
    assert protocol._json_serializer(model) == {"value": 3}

    class Dummy:
        def __init__(self):
            self.value = 4

    assert protocol._json_serializer(Dummy()) == {"value": 4}


def test_json_serializer_rejects_unknown_types():
    class Dummy:
        __slots__ = ()

    try:
        protocol._json_serializer(Dummy())
    except TypeError as exc:
        assert "not JSON serializable" in str(exc)


def test_wrap_and_extract_result_round_trip():
    result = ExecutionResult.success(result={"ok": True})
    wrapped = protocol.wrap_result_for_stdout(result)
    extracted = protocol.extract_result_from_stdout(wrapped)

    assert extracted is not None
    assert extracted.status == ExecutionStatus.SUCCESS


def test_extract_result_handles_missing_markers():
    assert protocol.extract_result_from_stdout("no markers") is None


def test_extract_result_handles_invalid_json():
    bad = f"{protocol.RESULT_START_MARKER}\n{{bad json}}\n{protocol.RESULT_END_MARKER}\n"
    assert protocol.extract_result_from_stdout(bad) is None


def test_extract_result_handles_missing_end_marker():
    incomplete = f'{protocol.RESULT_START_MARKER}\n{{"ok": true}}\n'
    assert protocol.extract_result_from_stdout(incomplete) is None
