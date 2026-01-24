"""
Tactus Standard Library - Core Module

Provides abstract base classes, common models, and shared utilities
used across all stdlib primitives.

Base Classes:
- BaseClassifier: ABC for all classification strategies
- BaseExtractor: ABC for all extraction strategies

Models:
- ClassifierResult: Result from any classifier
- ExtractorResult: Result from any extractor
- EvaluationResult: Metrics from evaluation

Utilities:
- RetryWithFeedback: Retry logic with conversational feedback
- extract_confidence: Confidence extraction heuristics
- validate_output: Output validation
"""

from .base import (
    BaseClassifier,
    BaseExtractor,
    ClassifierFactory,
    ExtractorFactory,
)
from .models import (
    ClassifierResult,
    ExtractorResult,
    EvaluationResult,
    ClassifierConfig,
    ExtractorConfig,
)
from .retry import RetryWithFeedback
from .confidence import extract_confidence
from .validation import validate_output

__all__ = [
    # Base classes
    "BaseClassifier",
    "BaseExtractor",
    # Factories
    "ClassifierFactory",
    "ExtractorFactory",
    # Result models
    "ClassifierResult",
    "ExtractorResult",
    "EvaluationResult",
    # Config models
    "ClassifierConfig",
    "ExtractorConfig",
    # Utilities
    "RetryWithFeedback",
    "extract_confidence",
    "validate_output",
]
