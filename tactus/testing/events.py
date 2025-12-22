"""
Structured log events for IDE integration.

Provides Pydantic models for test and evaluation events
that can be emitted as structured logs for IDE display.
"""

from datetime import datetime
from typing import List
from pydantic import BaseModel, Field

from .models import TestResult, EvaluationResult


class TestStartedEvent(BaseModel):
    """Event emitted when tests start."""

    event_type: str = "test_started"
    procedure_file: str
    total_scenarios: int
    timestamp: datetime = Field(default_factory=datetime.now)


class TestCompletedEvent(BaseModel):
    """Event emitted when tests complete."""

    event_type: str = "test_completed"
    result: TestResult
    timestamp: datetime = Field(default_factory=datetime.now)


class TestScenarioStartedEvent(BaseModel):
    """Event emitted when a scenario starts."""

    event_type: str = "test_scenario_started"
    scenario_name: str
    timestamp: datetime = Field(default_factory=datetime.now)


class TestScenarioCompletedEvent(BaseModel):
    """Event emitted when a scenario completes."""

    event_type: str = "test_scenario_completed"
    scenario_name: str
    status: str  # passed, failed, skipped
    duration: float
    total_cost: float = 0.0  # Total LLM cost for this scenario
    total_tokens: int = 0  # Total tokens used in this scenario
    timestamp: datetime = Field(default_factory=datetime.now)


class EvaluationStartedEvent(BaseModel):
    """Event emitted when evaluation starts."""

    event_type: str = "evaluation_started"
    procedure_file: str
    total_scenarios: int
    runs_per_scenario: int
    timestamp: datetime = Field(default_factory=datetime.now)


class EvaluationCompletedEvent(BaseModel):
    """Event emitted when evaluation completes."""

    event_type: str = "evaluation_completed"
    results: List[EvaluationResult]
    timestamp: datetime = Field(default_factory=datetime.now)


class EvaluationScenarioStartedEvent(BaseModel):
    """Event emitted when scenario evaluation starts."""

    event_type: str = "evaluation_scenario_started"
    scenario_name: str
    runs: int
    timestamp: datetime = Field(default_factory=datetime.now)


class EvaluationScenarioCompletedEvent(BaseModel):
    """Event emitted when scenario evaluation completes."""

    event_type: str = "evaluation_scenario_completed"
    result: EvaluationResult
    timestamp: datetime = Field(default_factory=datetime.now)


class EvaluationProgressEvent(BaseModel):
    """Event emitted during evaluation progress."""

    event_type: str = "evaluation_progress"
    scenario_name: str
    completed_runs: int
    total_runs: int
    timestamp: datetime = Field(default_factory=datetime.now)
