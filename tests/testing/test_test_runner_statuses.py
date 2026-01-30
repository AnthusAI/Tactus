from pathlib import Path

from tactus.testing.models import ParsedFeature, ParsedScenario, ScenarioResult, StepResult
from tactus.testing.test_runner import TactusTestRunner


def test_convert_json_scenario_result_coerces_error_message_dict():
    scenario_data = {
        "name": "Scenario",
        "status": "failed",
        "steps": [
            {
                "keyword": "Given ",
                "name": "step",
                "result": {"status": "failed", "duration": 1.0, "error_message": {"err": "x"}},
            }
        ],
        "tags": [],
    }

    result = TactusTestRunner._convert_json_scenario_result(scenario_data)

    assert result.steps[0].error_message == "{'err': 'x'}"


def test_build_feature_result_status_failed_and_skipped(tmp_path):
    runner = TactusTestRunner(Path(tmp_path / "proc.tac"))
    runner.parsed_feature = ParsedFeature(
        name="Feature",
        scenarios=[ParsedScenario(name="Scenario")],
    )

    failed = ScenarioResult(
        name="Scenario",
        status="failed",
        duration=1.0,
        steps=[StepResult(keyword="Given", message="x", status="failed")],
    )
    skipped = ScenarioResult(
        name="Scenario",
        status="skipped",
        duration=1.0,
        steps=[StepResult(keyword="Given", message="x", status="skipped")],
    )

    assert runner._build_feature_result([failed]).status == "failed"
    assert runner._build_feature_result([skipped]).status == "skipped"
