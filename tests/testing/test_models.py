"""
Tests for BDD testing models.
"""

from datetime import datetime

from tactus.testing.models import (
    ParsedStep,
    ParsedScenario,
    ParsedFeature,
    StepResult,
    ScenarioResult,
    FeatureResult,
    TestResult,
    EvaluationResult,
)


def test_parsed_step_creation():
    """Test creating a ParsedStep."""
    step = ParsedStep(
        keyword="Given",
        text="a precondition",
        line=5,
    )

    assert step.keyword == "Given"
    assert step.text == "a precondition"
    assert step.line == 5


def test_parsed_scenario_creation():
    """Test creating a ParsedScenario."""
    steps = [
        ParsedStep(keyword="Given", text="setup"),
        ParsedStep(keyword="Then", text="verify"),
    ]

    scenario = ParsedScenario(
        name="Test Scenario",
        tags=["@smoke"],
        steps=steps,
        line=10,
    )

    assert scenario.name == "Test Scenario"
    assert len(scenario.steps) == 2
    assert "@smoke" in scenario.tags


def test_parsed_feature_creation():
    """Test creating a ParsedFeature."""
    scenario = ParsedScenario(
        name="Test Scenario",
        steps=[ParsedStep(keyword="Given", text="setup")],
    )

    feature = ParsedFeature(
        name="Test Feature",
        description="Feature description",
        scenarios=[scenario],
        tags=["@important"],
    )

    assert feature.name == "Test Feature"
    assert feature.description == "Feature description"
    assert len(feature.scenarios) == 1
    assert "@important" in feature.tags


def test_step_result_creation():
    """Test creating a StepResult."""
    result = StepResult(
        keyword="Given",
        text="a precondition",
        status="passed",
        duration=0.5,
    )

    assert result.keyword == "Given"
    assert result.text == "a precondition"
    assert result.status == "passed"
    assert result.duration == 0.5
    assert result.error_message is None


def test_scenario_result_creation():
    """Test creating a ScenarioResult."""
    steps = [
        StepResult(keyword="Given", text="setup", status="passed", duration=0.1),
        StepResult(keyword="Then", text="verify", status="passed", duration=0.2),
    ]

    result = ScenarioResult(
        name="Test Scenario",
        status="passed",
        duration=0.3,
        steps=steps,
        tags=["@smoke"],
    )

    assert result.name == "Test Scenario"
    assert result.status == "passed"
    assert result.duration == 0.3
    assert len(result.steps) == 2
    assert isinstance(result.timestamp, datetime)


def test_test_result_creation():
    """Test creating a TestResult."""
    feature = FeatureResult(
        name="Test Feature",
        status="passed",
        duration=1.0,
        scenarios=[],
    )

    result = TestResult(
        features=[feature],
        total_scenarios=5,
        passed_scenarios=4,
        failed_scenarios=1,
        total_duration=10.0,
    )

    assert len(result.features) == 1
    assert result.total_scenarios == 5
    assert result.passed_scenarios == 4
    assert result.failed_scenarios == 1
    assert result.total_duration == 10.0


def test_evaluation_result_creation():
    """Test creating an EvaluationResult."""
    scenario_result = ScenarioResult(
        name="Test",
        status="passed",
        duration=1.0,
        steps=[],
    )

    result = EvaluationResult(
        scenario_name="Test Scenario",
        total_runs=10,
        passed_runs=9,
        failed_runs=1,
        success_rate=0.9,
        mean_duration=1.5,
        median_duration=1.4,
        stddev_duration=0.2,
        consistency_score=0.95,
        is_flaky=True,
        individual_results=[scenario_result],
    )

    assert result.scenario_name == "Test Scenario"
    assert result.total_runs == 10
    assert result.success_rate == 0.9
    assert result.consistency_score == 0.95
    assert result.is_flaky is True
    assert len(result.individual_results) == 1
