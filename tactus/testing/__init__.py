"""
Tactus BDD Testing Framework.

Provides Gherkin-style BDD testing integrated into the Tactus DSL.
"""

from .models import (
    StepResult,
    ScenarioResult,
    FeatureResult,
    TestResult,
    EvaluationResult,
    ParsedStep,
    ParsedScenario,
    ParsedFeature,
)
from .gherkin_parser import GherkinParser
from .test_runner import TactusTestRunner
from .evaluation_runner import TactusEvaluationRunner
from .context import TactusTestContext
from .mock_tools import MockToolRegistry, MockedToolPrimitive, create_default_mocks
from .mock_hitl import MockHITLHandler
from .events import (
    TestStartedEvent,
    TestCompletedEvent,
    TestScenarioStartedEvent,
    TestScenarioCompletedEvent,
    EvaluationStartedEvent,
    EvaluationCompletedEvent,
    EvaluationScenarioStartedEvent,
    EvaluationScenarioCompletedEvent,
    EvaluationProgressEvent,
)

__all__ = [
    "StepResult",
    "ScenarioResult",
    "FeatureResult",
    "TestResult",
    "EvaluationResult",
    "ParsedStep",
    "ParsedScenario",
    "ParsedFeature",
    "GherkinParser",
    "TactusTestRunner",
    "TactusEvaluationRunner",
    "TactusTestContext",
    "MockToolRegistry",
    "MockedToolPrimitive",
    "create_default_mocks",
    "MockHITLHandler",
    "TestStartedEvent",
    "TestCompletedEvent",
    "TestScenarioStartedEvent",
    "TestScenarioCompletedEvent",
    "EvaluationStartedEvent",
    "EvaluationCompletedEvent",
    "EvaluationScenarioStartedEvent",
    "EvaluationScenarioCompletedEvent",
    "EvaluationProgressEvent",
]
