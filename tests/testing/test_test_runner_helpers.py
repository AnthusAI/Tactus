from pathlib import Path

from tactus.testing.models import ParsedFeature, ParsedScenario, ScenarioResult, StepResult
from tactus.testing.test_runner import TactusTestRunner


def test_convert_json_scenario_result_handles_error_messages(tmp_path):
    scenario_data = {
        "name": "Example",
        "status": "failed",
        "tags": ["@fast"],
        "steps": [
            {
                "keyword": "Given ",
                "name": "a step",
                "result": {"status": "failed", "duration": 1.5, "error_message": ["a", "b"]},
            }
        ],
        "total_cost": 1.25,
        "total_tokens": 10,
        "iterations": 2,
        "tools_used": ["tool"],
        "llm_calls": 1,
    }

    result = TactusTestRunner._convert_json_scenario_result(scenario_data)

    assert result.duration == 1.5
    assert result.steps[0].error_message == "a\nb"
    assert result.tags == ["fast"]
    assert result.total_cost == 1.25
    assert result.total_tokens == 10
    assert result.iterations == 2
    assert result.tools_used == ["tool"]
    assert result.llm_calls == 1


def test_convert_json_scenario_result_coerces_non_string_error(tmp_path):
    scenario_data = {
        "name": "Example",
        "status": "failed",
        "steps": [
            {
                "keyword": "Given ",
                "name": "a step",
                "result": {"status": "failed", "duration": 0.5, "error_message": 123},
            }
        ],
    }

    result = TactusTestRunner._convert_json_scenario_result(scenario_data)

    assert result.steps[0].error_message == "123"


def test_convert_json_scenario_result_accepts_string_error(tmp_path):
    scenario_data = {
        "name": "Example",
        "status": "failed",
        "steps": [
            {
                "keyword": "Given ",
                "name": "a step",
                "result": {"status": "failed", "duration": 0.5, "error_message": "oops"},
            }
        ],
    }

    result = TactusTestRunner._convert_json_scenario_result(scenario_data)

    assert result.steps[0].error_message == "oops"


def test_convert_scenario_result_handles_iterations_callable(tmp_path):
    class Status:
        name = "passed"

    class Step:
        def __init__(self):
            self.keyword = "Given"
            self.name = "ok"
            self.status = Status()
            self.duration = 0.5

    class BehaveScenario:
        name = "Scenario"
        status = Status()
        duration = 2.0
        steps = [Step()]
        tags = ["smoke"]
        total_cost = 0.2
        total_tokens = 5
        cost_breakdown = [{"cost": 0.1}, {"cost": 0.1}]
        tools_used = ["tool"]

        def iterations(self):
            return 3

    result = TactusTestRunner._convert_scenario_result(BehaveScenario())

    assert result.iterations == 3
    assert result.llm_calls == 2
    assert result.steps[0].status == "passed"


def test_build_feature_and_test_results(tmp_path):
    runner = TactusTestRunner(Path(tmp_path / "proc.tac"))
    runner.parsed_feature = ParsedFeature(
        name="Feature",
        description="Desc",
        scenarios=[ParsedScenario(name="Scenario")],
        tags=["tag"],
    )

    scenario_results = [
        ScenarioResult(
            name="Scenario",
            status="passed",
            duration=1.0,
            steps=[StepResult(keyword="Given", message="x", status="passed")],
            total_cost=0.1,
            total_tokens=2,
            iterations=1,
            tools_used=["tool"],
            llm_calls=1,
        )
    ]

    feature_result = runner._build_feature_result(scenario_results)
    test_result = runner._build_test_result([feature_result])

    assert feature_result.status == "passed"
    assert feature_result.duration == 1.0
    assert test_result.total_scenarios == 1
    assert test_result.passed_scenarios == 1
    assert test_result.total_cost == 0.1
    assert test_result.unique_tools_used == ["tool"]
