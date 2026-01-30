import pytest

from tactus.stdlib.core.base import (
    BaseClassifier,
    BaseExtractor,
    ClassifierFactory,
    ExtractorFactory,
)
from tactus.stdlib.core.models import ClassifierResult, ExtractorResult


class DummyClassifier(BaseClassifier):
    classes = ["yes", "no"]
    target_classes = ["yes"]

    def classify(self, input_text: str) -> ClassifierResult:
        value = "yes" if "yes" in input_text else "no"
        return ClassifierResult(value=value, confidence=0.9)


class DummyExtractor(BaseExtractor):
    def extract(self, input_text: str) -> ExtractorResult:
        return ExtractorResult(fields={"text": input_text})


class DummyClassifierNoTargets(BaseClassifier):
    def classify(self, input_text: str) -> ClassifierResult:
        return ClassifierResult(value="maybe", confidence=None)


class DummyClassifierError(BaseClassifier):
    def classify(self, input_text: str) -> ClassifierResult:
        raise RuntimeError(f"boom:{input_text}")


class DummyExtractorConfig(BaseExtractor):
    def __init__(self, config=None, **kwargs):
        self.config = config or {}
        self.extra = kwargs

    def extract(self, input_text: str) -> ExtractorResult:
        return ExtractorResult(fields={"text": input_text})


class DummyClassifierConfig(BaseClassifier):
    def __init__(self, config=None, **kwargs):
        self.config = config or {}
        self.extra = kwargs

    def classify(self, input_text: str) -> ClassifierResult:
        return ClassifierResult(value="yes", confidence=0.5)


def test_classifier_callable_and_evaluate():
    classifier = DummyClassifier()
    assert classifier({"text": "yes"}).value == "yes"

    data = [
        {"text": "yes", "label": "yes"},
        {"text": "no", "label": "no"},
    ]
    result = DummyClassifier.evaluate(classifier, data)
    assert result.accuracy == 1.0
    assert result.precision == 1.0
    assert result.recall == 1.0


def test_extractor_callable():
    extractor = DummyExtractor()
    result = extractor({"text": "hello"})
    assert result.fields["text"] == "hello"


def test_classifier_callable_accepts_string_and_input_key():
    classifier = DummyClassifier()
    assert classifier({"input": "yes"}).value == "yes"
    assert classifier("no").value == "no"
    classifier.reset()


def test_extractor_callable_accepts_input_key_and_string():
    extractor = DummyExtractor()
    assert extractor({"input": "hello"}).fields["text"] == "hello"
    assert extractor("world").fields["text"] == "world"
    extractor.reset()


def test_classifier_evaluate_handles_empty_data():
    classifier = DummyClassifier()
    result = DummyClassifier.evaluate(classifier, [])
    assert result.accuracy == 0.0
    assert result.total_samples == 0
    assert result.mean_confidence is None


def test_classifier_evaluate_without_target_classes():
    classifier = DummyClassifierNoTargets()
    data = [{"text": "anything", "label": "maybe"}]
    result = DummyClassifierNoTargets.evaluate(classifier, data)
    assert result.precision is None
    assert result.recall is None
    assert result.f1 is None


def test_classifier_evaluate_records_errors():
    classifier = DummyClassifierError()
    data = [{"text": "oops", "label": "yes"}]
    result = DummyClassifierError.evaluate(classifier, data)
    assert result.accuracy == 0.0
    assert result.errors
    assert result.confusion_matrix["yes"]["ERROR"] == 1


def test_classifier_factory_registers_and_creates():
    ClassifierFactory.register("dummy", DummyClassifierConfig)
    classifier = ClassifierFactory.create({"method": "dummy", "value": 1}, foo="bar")
    assert isinstance(classifier, DummyClassifierConfig)
    assert classifier.config["value"] == 1
    assert classifier.extra["foo"] == "bar"
    assert "dummy" in ClassifierFactory.available_methods()


def test_classifier_factory_unknown_method():
    with pytest.raises(ValueError, match="Unknown classifier method"):
        ClassifierFactory.create({"method": "missing"})


def test_extractor_factory_registers_and_creates():
    ExtractorFactory.register("dummy", DummyExtractorConfig)
    extractor = ExtractorFactory.create({"method": "dummy"}, foo="bar")
    assert isinstance(extractor, DummyExtractorConfig)
    assert extractor.extra["foo"] == "bar"
    assert "dummy" in ExtractorFactory.available_methods()


def test_extractor_factory_unknown_method():
    with pytest.raises(ValueError, match="Unknown extractor method"):
        ExtractorFactory.create({"method": "missing"})
