import pytest

from tactus.testing.evaluation_runner import TactusEvaluationRunner


def test_evaluate_all_requires_setup(tmp_path):
    runner = TactusEvaluationRunner(tmp_path / "proc.tac")
    with pytest.raises(RuntimeError):
        runner.evaluate_all()


def test_evaluate_scenario_requires_setup(tmp_path):
    runner = TactusEvaluationRunner(tmp_path / "proc.tac")
    with pytest.raises(RuntimeError):
        runner.evaluate_scenario("scenario")
