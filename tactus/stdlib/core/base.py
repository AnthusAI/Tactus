"""
Abstract base classes for stdlib primitives.

These ABCs define the interface that all classifiers and extractors must implement,
enabling polymorphism and consistent behavior across different implementations.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type

from .models import ClassifierResult, ExtractorResult, EvaluationResult


class BaseClassifier(ABC):
    """
    Abstract base class for all classification strategies.

    Subclasses must implement the `classify` method. This enables:
    - LLMClassifier: Uses LLM with retry logic
    - FuzzyMatchClassifier: Uses string similarity
    - Custom classifiers: User-defined implementations

    All classifiers return ClassifierResult for consistent API.

    Example:
        class MyClassifier(BaseClassifier):
            def classify(self, input_text: str) -> ClassifierResult:
                # Custom classification logic
                return ClassifierResult(value="Yes", confidence=0.9)
    """

    # Configuration (set by subclasses)
    classes: List[str] = []
    target_classes: List[str] = []
    name: Optional[str] = None

    @abstractmethod
    def classify(self, input_text: str) -> ClassifierResult:
        """
        Classify the input text and return a result.

        Args:
            input_text: The text to classify

        Returns:
            ClassifierResult with value, confidence, explanation, etc.
        """
        ...

    def __call__(self, input_value: Any) -> ClassifierResult:
        """
        Make classifiers callable.

        Handles both string input and dict input (for Lua interop).

        Args:
            input_value: Either a string or dict with 'text'/'input' key

        Returns:
            ClassifierResult
        """
        if isinstance(input_value, dict):
            text = input_value.get("text") or input_value.get("input") or str(input_value)
        else:
            text = str(input_value)

        return self.classify(text)

    def reset(self) -> None:
        """
        Reset any internal state (e.g., conversation history).

        Override in subclasses that maintain state.
        """
        pass

    @classmethod
    def evaluate(
        cls,
        classifier: "BaseClassifier",
        test_data: List[Dict[str, Any]],
        label_key: str = "label",
        input_key: str = "text",
    ) -> EvaluationResult:
        """
        Evaluate a classifier on test data.

        Args:
            classifier: The classifier instance to evaluate
            test_data: List of dicts with input text and expected labels
            label_key: Key for expected label in test data
            input_key: Key for input text in test data

        Returns:
            EvaluationResult with accuracy, precision, recall, F1
        """
        from collections import defaultdict

        predictions = []
        labels = []
        total_retries = 0
        confidences = []
        errors = []

        for item in test_data:
            text = item.get(input_key, "")
            expected = item.get(label_key)

            try:
                result = classifier.classify(text)
                predictions.append(result.value)
                labels.append(expected)
                total_retries += result.retry_count
                if result.confidence is not None:
                    confidences.append(result.confidence)
            except Exception as e:
                errors.append(f"Error on item: {str(e)}")
                predictions.append("ERROR")
                labels.append(expected)

        # Calculate accuracy
        correct = sum(pred == label for pred, label in zip(predictions, labels))
        accuracy = correct / len(test_data) if test_data else 0.0

        # Calculate confusion matrix
        confusion: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for pred, label in zip(predictions, labels):
            confusion[label][pred] += 1

        # Calculate precision/recall for target classes
        precision = None
        recall = None
        f1 = None

        if classifier.target_classes:
            # True positives: predicted target AND was target
            tp = sum(
                1
                for pred, label in zip(predictions, labels)
                if pred in classifier.target_classes and label in classifier.target_classes
            )
            # False positives: predicted target BUT was NOT target
            fp = sum(
                1
                for pred, label in zip(predictions, labels)
                if pred in classifier.target_classes and label not in classifier.target_classes
            )
            # False negatives: did NOT predict target BUT was target
            fn = sum(
                1
                for pred, label in zip(predictions, labels)
                if pred not in classifier.target_classes and label in classifier.target_classes
            )

            precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

        return EvaluationResult(
            accuracy=accuracy,
            precision=precision,
            recall=recall,
            f1=f1,
            confusion_matrix=dict(confusion),
            total_samples=len(test_data),
            total_retries=total_retries,
            mean_confidence=sum(confidences) / len(confidences) if confidences else None,
            errors=errors,
        )


class BaseExtractor(ABC):
    """
    Abstract base class for all extraction strategies.

    Subclasses must implement the `extract` method. This enables:
    - LLMExtractor: Uses LLM with retry logic
    - SchemaExtractor: Uses structured schema parsing
    - Custom extractors: User-defined implementations

    All extractors return ExtractorResult for consistent API.

    Example:
        class MyExtractor(BaseExtractor):
            def extract(self, input_text: str) -> ExtractorResult:
                # Custom extraction logic
                return ExtractorResult(fields={"name": "John", "age": 30})
    """

    # Configuration (set by subclasses)
    fields: Dict[str, str] = {}
    name: Optional[str] = None

    @abstractmethod
    def extract(self, input_text: str) -> ExtractorResult:
        """
        Extract structured data from the input text.

        Args:
            input_text: The text to extract from

        Returns:
            ExtractorResult with fields dict and validation info
        """
        ...

    def __call__(self, input_value: Any) -> ExtractorResult:
        """
        Make extractors callable.

        Handles both string input and dict input (for Lua interop).

        Args:
            input_value: Either a string or dict with 'text'/'input' key

        Returns:
            ExtractorResult
        """
        if isinstance(input_value, dict):
            text = input_value.get("text") or input_value.get("input") or str(input_value)
        else:
            text = str(input_value)

        return self.extract(text)

    def reset(self) -> None:
        """
        Reset any internal state.

        Override in subclasses that maintain state.
        """
        pass


class ClassifierFactory:
    """
    Factory for creating classifiers based on configuration.

    Supports registration of custom classifier types.
    """

    _registry: Dict[str, Type[BaseClassifier]] = {}

    @classmethod
    def register(cls, method: str, classifier_class: Type[BaseClassifier]) -> None:
        """Register a classifier type."""
        cls._registry[method] = classifier_class

    @classmethod
    def create(cls, config: Dict[str, Any], **kwargs) -> BaseClassifier:
        """
        Create a classifier from configuration.

        Args:
            config: Configuration dict with 'method' key
            **kwargs: Additional kwargs passed to classifier constructor

        Returns:
            BaseClassifier instance

        Raises:
            ValueError: If method is not registered
        """
        method = config.get("method", "llm")

        if method not in cls._registry:
            available = ", ".join(cls._registry.keys())
            raise ValueError(f"Unknown classifier method: '{method}'. Available: {available}")

        classifier_class = cls._registry[method]
        return classifier_class(config=config, **kwargs)

    @classmethod
    def available_methods(cls) -> List[str]:
        """Get list of available classifier methods."""
        return list(cls._registry.keys())


class ExtractorFactory:
    """
    Factory for creating extractors based on configuration.

    Supports registration of custom extractor types.
    """

    _registry: Dict[str, Type[BaseExtractor]] = {}

    @classmethod
    def register(cls, method: str, extractor_class: Type[BaseExtractor]) -> None:
        """Register an extractor type."""
        cls._registry[method] = extractor_class

    @classmethod
    def create(cls, config: Dict[str, Any], **kwargs) -> BaseExtractor:
        """
        Create an extractor from configuration.

        Args:
            config: Configuration dict with 'method' key
            **kwargs: Additional kwargs passed to extractor constructor

        Returns:
            BaseExtractor instance

        Raises:
            ValueError: If method is not registered
        """
        method = config.get("method", "llm")

        if method not in cls._registry:
            available = ", ".join(cls._registry.keys())
            raise ValueError(f"Unknown extractor method: '{method}'. Available: {available}")

        extractor_class = cls._registry[method]
        return extractor_class(config=config, **kwargs)

    @classmethod
    def available_methods(cls) -> List[str]:
        """Get list of available extractor methods."""
        return list(cls._registry.keys())
