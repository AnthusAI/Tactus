"""
Pydantic models for BDD testing results and parsed Gherkin.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


# Parsed Gherkin Models (from gherkin-official)


class ParsedStep(BaseModel):
    """Parsed Gherkin step."""

    keyword: str  # Given, When, Then, And, But
    text: str
    line: Optional[int] = None


class ParsedScenario(BaseModel):
    """Parsed Gherkin scenario."""

    name: str
    tags: List[str] = Field(default_factory=list)
    steps: List[ParsedStep] = Field(default_factory=list)
    line: Optional[int] = None


class ParsedFeature(BaseModel):
    """Parsed Gherkin feature."""

    name: str
    description: str = ""
    scenarios: List[ParsedScenario] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    line: Optional[int] = None


# Test Result Models (from Behave execution)


class StepResult(BaseModel):
    """Result of executing a single step."""

    keyword: str
    text: str
    status: str  # passed, failed, skipped, undefined
    duration: float = 0.0
    error_message: Optional[str] = None


class ScenarioResult(BaseModel):
    """Result of executing a scenario."""

    name: str
    status: str  # passed, failed, skipped
    duration: float
    steps: List[StepResult] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    iteration: Optional[int] = None  # For evaluation runs
    timestamp: datetime = Field(default_factory=datetime.now)


class FeatureResult(BaseModel):
    """Result of executing a feature."""

    name: str
    description: str = ""
    status: str  # passed, failed, skipped
    duration: float
    scenarios: List[ScenarioResult] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)


class TestResult(BaseModel):
    """Result from 'tactus test' command."""

    features: List[FeatureResult] = Field(default_factory=list)
    total_scenarios: int
    passed_scenarios: int
    failed_scenarios: int
    total_duration: float


class EvaluationResult(BaseModel):
    """Result from 'tactus evaluate' command."""

    scenario_name: str
    total_runs: int
    passed_runs: int
    failed_runs: int
    success_rate: float
    mean_duration: float
    median_duration: float
    stddev_duration: float
    consistency_score: float  # 0.0 to 1.0
    is_flaky: bool
    individual_results: List[ScenarioResult] = Field(default_factory=list)
