from tactus.stdlib.core.retry import (
    RetryWithFeedback,
    create_classification_validator,
    create_classification_feedback,
)


def test_retry_with_feedback_success_first_attempt():
    retry = RetryWithFeedback(max_retries=2)

    result = retry.execute(
        call_fn=lambda msg: "Yes",
        initial_message="msg",
        validate_fn=create_classification_validator(["Yes", "No"]),
        build_feedback_fn=create_classification_feedback(["Yes", "No"]),
    )
    assert result["success"] is True
    assert result["retry_count"] == 0
    assert result["response"] == "Yes"


def test_retry_with_feedback_exhausts_retries():
    retries = []

    def on_retry(count, response, feedback):
        retries.append((count, response))

    retry = RetryWithFeedback(max_retries=1, on_retry=on_retry)
    result = retry.execute(
        call_fn=lambda msg: "maybe",
        initial_message="msg",
        validate_fn=create_classification_validator(["yes"]),
        build_feedback_fn=create_classification_feedback(["yes"]),
    )
    assert result["success"] is False
    assert result["retry_count"] == 1
    assert retries


def test_retry_with_feedback_retries_without_callback():
    calls = []

    def call_fn(msg):
        calls.append(msg)
        return "No" if len(calls) > 1 else "maybe"

    retry = RetryWithFeedback(max_retries=1)
    result = retry.execute(
        call_fn=call_fn,
        initial_message="msg",
        validate_fn=create_classification_validator(["yes", "no"]),
        build_feedback_fn=create_classification_feedback(["yes", "no"]),
    )

    assert result["success"] is True
    assert result["retry_count"] == 1


def test_classification_validator_empty_and_prefix():
    validator = create_classification_validator(["yes", "no"])
    assert validator("") is False
    assert validator("yes - because") is True
