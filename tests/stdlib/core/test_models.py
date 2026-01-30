from tactus.stdlib.core.models import ClassifierResult, ExtractorResult


def test_classifier_result_is_error():
    assert ClassifierResult(value="ERROR").is_error is True
    assert ClassifierResult(value="ok", error="oops").is_error is True
    assert ClassifierResult(value="ok").is_error is False


def test_extractor_result_is_valid():
    assert ExtractorResult(fields={"a": 1}).is_valid is True
    assert ExtractorResult(validation_errors=["missing"]).is_valid is False
    assert ExtractorResult(error="boom").is_valid is False


def test_extractor_result_to_dict_alias():
    result = ExtractorResult(fields={"a": 1}, validation_errors=["oops"], retry_count=2)
    data = result.to_dict()

    assert data["a"] == 1
    assert data["_validation_errors"] == ["oops"]
    assert data["_retry_count"] == 2
