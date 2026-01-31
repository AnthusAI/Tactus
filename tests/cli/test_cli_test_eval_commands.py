from types import SimpleNamespace
import os

import pytest
import typer
from typer.testing import CliRunner

from tactus.cli import app as cli_app


class FakeValidator:
    def __init__(self, result):
        self._result = result

    def validate_file(self, path):
        return self._result


@pytest.fixture
def cli_runner():
    return CliRunner()


class DummyConsole:
    def __init__(self):
        self.lines = []

    def print(self, *args, **kwargs):
        self.lines.append(" ".join(str(a) for a in args))


class DummyScenario:
    def __init__(
        self, name, status, duration, total_cost=0, llm_calls=0, iterations=0, tools_used=None
    ):
        self.name = name
        self.status = status
        self.duration = duration
        self.total_cost = total_cost
        self.llm_calls = llm_calls
        self.iterations = iterations
        self.tools_used = tools_used or []
        self.steps = []


class DummyStep:
    def __init__(self, keyword, message, status="failed", error_message=None):
        self.keyword = keyword
        self.message = message
        self.status = status
        self.error_message = error_message


class DummyFeature:
    def __init__(self, name, scenarios):
        self.name = name
        self.scenarios = scenarios


class DummyEvalResult:
    def __init__(self, name, success_rate=0.5):
        self.scenario_name = name
        self.success_rate = success_rate
        self.passed_runs = 1
        self.total_runs = 2
        self.mean_duration = 1.2
        self.stddev_duration = 0.1
        self.consistency_score = 0.8
        self.is_flaky = True


def test_cli_test_command_requires_specs(monkeypatch, tmp_path, cli_runner):
    monkeypatch.setattr(cli_app, "setup_logging", lambda verbose: None)

    class FakeConfigManager:
        def load_cascade(self, path):
            return {}

    monkeypatch.setattr("tactus.core.config_manager.ConfigManager", lambda: FakeConfigManager())

    registry = SimpleNamespace(gherkin_specifications=None)
    result = SimpleNamespace(valid=True, registry=registry, errors=[])
    monkeypatch.setattr("tactus.validation.TactusValidator", lambda: FakeValidator(result))

    path = tmp_path / "sample.tac"
    path.write_text("content")

    result = cli_runner.invoke(cli_app.app, ["test", str(path)])
    assert result.exit_code == 1
    assert "no specifications" in result.stdout.lower()


def test_cli_test_command_runs_runner(monkeypatch, tmp_path, cli_runner):
    monkeypatch.setattr(cli_app, "setup_logging", lambda verbose: None)

    class FakeConfigManager:
        def load_cascade(self, path):
            return {}

    monkeypatch.setattr("tactus.core.config_manager.ConfigManager", lambda: FakeConfigManager())

    registry = SimpleNamespace(gherkin_specifications="Feature: A\nScenario: B", custom_steps={})
    result = SimpleNamespace(valid=True, registry=registry, errors=[])
    monkeypatch.setattr("tactus.validation.TactusValidator", lambda: FakeValidator(result))

    class FakeRunner:
        def __init__(self, *args, **kwargs):
            pass

        def setup(self, *args, **kwargs):
            return None

        def run_tests(self, *args, **kwargs):
            return SimpleNamespace(
                features=[],
                total_scenarios=1,
                passed_scenarios=1,
                failed_scenarios=0,
                total_cost=0,
                total_llm_calls=0,
                total_iterations=0,
                unique_tools_used=[],
            )

        def cleanup(self):
            return None

    monkeypatch.setattr("tactus.testing.test_runner.TactusTestRunner", FakeRunner)

    path = tmp_path / "sample.tac"
    path.write_text("content")

    result = cli_runner.invoke(cli_app.app, ["test", str(path)])
    assert result.exit_code == 0


def test_cli_test_command_missing_file(cli_runner):
    result = cli_runner.invoke(cli_app.app, ["test", "missing.tac"])
    assert result.exit_code == 1


def test_cli_test_command_validation_failure(monkeypatch, tmp_path, cli_runner):
    monkeypatch.setattr(cli_app, "setup_logging", lambda verbose: None)

    class FakeConfigManager:
        def load_cascade(self, path):
            return {}

    monkeypatch.setattr("tactus.core.config_manager.ConfigManager", lambda: FakeConfigManager())

    result = SimpleNamespace(valid=False, registry=None, errors=[SimpleNamespace(message="bad")])
    monkeypatch.setattr("tactus.validation.TactusValidator", lambda: FakeValidator(result))

    path = tmp_path / "sample.tac"
    path.write_text("content")

    result = cli_runner.invoke(cli_app.app, ["test", str(path)])
    assert result.exit_code == 1


def test_cli_test_command_no_specifications(monkeypatch, tmp_path, cli_runner):
    monkeypatch.setattr(cli_app, "setup_logging", lambda verbose: None)

    class FakeConfigManager:
        def load_cascade(self, path):
            return {}

    monkeypatch.setattr("tactus.core.config_manager.ConfigManager", lambda: FakeConfigManager())

    registry = SimpleNamespace(gherkin_specifications=None, custom_steps={})
    result = SimpleNamespace(valid=True, registry=registry, errors=[])
    monkeypatch.setattr("tactus.validation.TactusValidator", lambda: FakeValidator(result))

    path = tmp_path / "sample.tac"
    path.write_text("content")

    result = cli_runner.invoke(cli_app.app, ["test", str(path)])
    assert result.exit_code == 1
    assert "no specifications" in result.stdout.lower()


def test_cli_test_command_runs_evaluation(monkeypatch, tmp_path, cli_runner):
    monkeypatch.setattr(cli_app, "setup_logging", lambda verbose: None)

    class FakeConfigManager:
        def load_cascade(self, path):
            return {"openai_api_key": "key"}

    monkeypatch.setattr("tactus.core.config_manager.ConfigManager", lambda: FakeConfigManager())

    registry = SimpleNamespace(gherkin_specifications="Feature: A\nScenario: B", custom_steps={})
    result = SimpleNamespace(valid=True, registry=registry, errors=[])
    monkeypatch.setattr("tactus.validation.TactusValidator", lambda: FakeValidator(result))

    class FakeEvalRunner:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

        def setup(self, *args, **kwargs):
            return None

        def evaluate_scenario(self, _scenario, _runs, _parallel):
            return SimpleNamespace(
                scenario_name="demo",
                success_rate=1.0,
                passed_runs=1,
                total_runs=1,
                mean_duration=0.1,
                stddev_duration=0.0,
                consistency_score=1.0,
                is_flaky=False,
            )

        def evaluate_all(self, _runs, _parallel):
            return [self.evaluate_scenario("demo", 1, True)]

        def cleanup(self):
            return None

    monkeypatch.setattr("tactus.testing.evaluation_runner.TactusEvaluationRunner", FakeEvalRunner)

    path = tmp_path / "sample.tac"
    path.write_text("content")

    monkeypatch.setenv("OPENAI_API_KEY", "preexisting")
    result = cli_runner.invoke(cli_app.app, ["test", str(path), "--runs", "2"])
    assert result.exit_code == 0
    assert os.environ.get("OPENAI_API_KEY") == "preexisting"


def test_cli_test_command_sets_env_from_config(monkeypatch, tmp_path, cli_runner):
    monkeypatch.setattr(cli_app, "setup_logging", lambda verbose: None)

    class FakeConfigManager:
        def load_cascade(self, path):
            return {"openai_api_key": "config-key"}

    monkeypatch.setattr("tactus.core.config_manager.ConfigManager", lambda: FakeConfigManager())

    registry = SimpleNamespace(gherkin_specifications="Feature: A\nScenario: B", custom_steps={})
    result = SimpleNamespace(valid=True, registry=registry, errors=[])
    monkeypatch.setattr("tactus.validation.TactusValidator", lambda: FakeValidator(result))

    class FakeRunner:
        def __init__(self, *args, **kwargs):
            pass

        def setup(self, *args, **kwargs):
            return None

        def run_tests(self, *args, **kwargs):
            return SimpleNamespace(
                features=[],
                total_scenarios=1,
                passed_scenarios=1,
                failed_scenarios=0,
                total_cost=0,
                total_llm_calls=0,
                total_iterations=0,
                unique_tools_used=[],
            )

        def cleanup(self):
            return None

    monkeypatch.setattr("tactus.testing.test_runner.TactusTestRunner", FakeRunner)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    path = tmp_path / "sample.tac"
    path.write_text("content")

    result = cli_runner.invoke(cli_app.app, ["test", str(path)])
    assert result.exit_code == 0
    assert os.environ.get("OPENAI_API_KEY") == "config-key"


def test_cli_test_command_mock_config(monkeypatch, tmp_path, cli_runner):
    monkeypatch.setattr(cli_app, "setup_logging", lambda verbose: None)

    class FakeConfigManager:
        def load_cascade(self, path):
            return {}

    monkeypatch.setattr("tactus.core.config_manager.ConfigManager", lambda: FakeConfigManager())

    registry = SimpleNamespace(gherkin_specifications="Feature: A\nScenario: B", custom_steps={})
    result = SimpleNamespace(valid=True, registry=registry, errors=[])
    monkeypatch.setattr("tactus.validation.TactusValidator", lambda: FakeValidator(result))

    class FakeRunner:
        def __init__(self, *args, **kwargs):
            pass

        def setup(self, *args, **kwargs):
            return None

        def run_tests(self, *args, **kwargs):
            return SimpleNamespace(
                features=[],
                total_scenarios=1,
                passed_scenarios=1,
                failed_scenarios=0,
                total_cost=0,
                total_llm_calls=0,
                total_iterations=0,
                unique_tools_used=[],
            )

        def cleanup(self):
            return None

    monkeypatch.setattr("tactus.testing.test_runner.TactusTestRunner", FakeRunner)

    mock_config = tmp_path / "mocks.json"
    mock_config.write_text('{"tool": {"type": "static"}}')

    path = tmp_path / "sample.tac"
    path.write_text("content")

    result = cli_runner.invoke(cli_app.app, ["test", str(path), "--mock-config", str(mock_config)])
    assert result.exit_code == 0


def test_cli_test_command_default_mocks(monkeypatch, tmp_path, cli_runner):
    monkeypatch.setattr(cli_app, "setup_logging", lambda verbose: None)

    class FakeConfigManager:
        def load_cascade(self, path):
            return {}

    monkeypatch.setattr("tactus.core.config_manager.ConfigManager", lambda: FakeConfigManager())

    registry = SimpleNamespace(gherkin_specifications="Feature: A\nScenario: B", custom_steps={})
    result = SimpleNamespace(valid=True, registry=registry, errors=[])
    monkeypatch.setattr("tactus.validation.TactusValidator", lambda: FakeValidator(result))

    called = {"default": False}

    def fake_default_mocks():
        called["default"] = True
        return {"tool": {}}

    monkeypatch.setattr("tactus.testing.mock_tools.create_default_mocks", fake_default_mocks)

    class FakeRunner:
        def __init__(self, *args, **kwargs):
            pass

        def setup(self, *args, **kwargs):
            return None

        def run_tests(self, *args, **kwargs):
            return SimpleNamespace(
                features=[],
                total_scenarios=1,
                passed_scenarios=1,
                failed_scenarios=0,
                total_cost=0,
                total_llm_calls=0,
                total_iterations=0,
                unique_tools_used=[],
            )

        def cleanup(self):
            return None

    monkeypatch.setattr("tactus.testing.test_runner.TactusTestRunner", FakeRunner)

    path = tmp_path / "sample.tac"
    path.write_text("content")

    result = cli_runner.invoke(cli_app.app, ["test", str(path), "--mock"])
    assert result.exit_code == 0
    assert called["default"] is True


def test_cli_test_command_parses_params(monkeypatch, tmp_path, cli_runner):
    monkeypatch.setattr(cli_app, "setup_logging", lambda verbose: None)

    class FakeConfigManager:
        def load_cascade(self, path):
            return {}

    monkeypatch.setattr("tactus.core.config_manager.ConfigManager", lambda: FakeConfigManager())

    registry = SimpleNamespace(gherkin_specifications="Feature: A\nScenario: B", custom_steps={})
    result = SimpleNamespace(valid=True, registry=registry, errors=[])
    monkeypatch.setattr("tactus.validation.TactusValidator", lambda: FakeValidator(result))

    captured = {}

    class FakeRunner:
        def __init__(self, _path, mock_tools, params):
            captured.update(params)

        def setup(self, *args, **kwargs):
            return None

        def run_tests(self, *args, **kwargs):
            return SimpleNamespace(
                features=[],
                total_scenarios=1,
                passed_scenarios=1,
                failed_scenarios=0,
                total_cost=0,
                total_llm_calls=0,
                total_iterations=0,
                unique_tools_used=[],
            )

        def cleanup(self):
            return None

    monkeypatch.setattr("tactus.testing.test_runner.TactusTestRunner", FakeRunner)

    path = tmp_path / "sample.tac"
    path.write_text("content")

    result = cli_runner.invoke(cli_app.app, ["test", str(path), "--param", "a=1"])
    assert result.exit_code == 0
    assert captured["a"] == "1"


def test_cli_test_command_ignores_bad_param(monkeypatch, tmp_path, cli_runner):
    monkeypatch.setattr(cli_app, "setup_logging", lambda verbose: None)

    class FakeConfigManager:
        def load_cascade(self, path):
            return {}

    monkeypatch.setattr("tactus.core.config_manager.ConfigManager", lambda: FakeConfigManager())

    registry = SimpleNamespace(gherkin_specifications="Feature: A\nScenario: B", custom_steps={})
    result = SimpleNamespace(valid=True, registry=registry, errors=[])
    monkeypatch.setattr("tactus.validation.TactusValidator", lambda: FakeValidator(result))

    class FakeRunner:
        def __init__(self, _path, mock_tools, params):
            self.params = params

        def setup(self, *args, **kwargs):
            return None

        def run_tests(self, *args, **kwargs):
            return SimpleNamespace(
                features=[],
                total_scenarios=1,
                passed_scenarios=1,
                failed_scenarios=0,
                total_cost=0,
                total_llm_calls=0,
                total_iterations=0,
                unique_tools_used=[],
            )

        def cleanup(self):
            return None

    monkeypatch.setattr("tactus.testing.test_runner.TactusTestRunner", FakeRunner)

    path = tmp_path / "sample.tac"
    path.write_text("content")

    result = cli_runner.invoke(cli_app.app, ["test", str(path), "--param", "oops"])
    assert result.exit_code == 0


def test_cli_test_command_runner_error_verbose(monkeypatch, tmp_path, cli_runner):
    monkeypatch.setattr(cli_app, "setup_logging", lambda verbose: None)

    class FakeConfigManager:
        def load_cascade(self, path):
            return {}

    monkeypatch.setattr("tactus.core.config_manager.ConfigManager", lambda: FakeConfigManager())

    registry = SimpleNamespace(gherkin_specifications="Feature: A\nScenario: B", custom_steps={})
    result = SimpleNamespace(valid=True, registry=registry, errors=[])
    monkeypatch.setattr("tactus.validation.TactusValidator", lambda: FakeValidator(result))

    class FakeRunner:
        def __init__(self, *args, **kwargs):
            pass

        def setup(self, *args, **kwargs):
            raise RuntimeError("boom")

        def run_tests(self, *args, **kwargs):
            raise AssertionError("should not run")

        def cleanup(self):
            return None

    monkeypatch.setattr("tactus.testing.test_runner.TactusTestRunner", FakeRunner)
    monkeypatch.setattr(cli_app.console, "print_exception", lambda *_args, **_kwargs: None)

    path = tmp_path / "sample.tac"
    path.write_text("content")

    result = cli_runner.invoke(cli_app.app, ["test", str(path), "--verbose"])
    assert result.exit_code == 1


def test_cli_test_command_failed_scenarios(monkeypatch, tmp_path, cli_runner):
    monkeypatch.setattr(cli_app, "setup_logging", lambda verbose: None)

    class FakeConfigManager:
        def load_cascade(self, path):
            return {}

    monkeypatch.setattr("tactus.core.config_manager.ConfigManager", lambda: FakeConfigManager())

    registry = SimpleNamespace(gherkin_specifications="Feature: A\nScenario: B", custom_steps={})
    result = SimpleNamespace(valid=True, registry=registry, errors=[])
    monkeypatch.setattr("tactus.validation.TactusValidator", lambda: FakeValidator(result))

    class FakeRunner:
        def __init__(self, *args, **kwargs):
            pass

        def setup(self, *args, **kwargs):
            return None

        def run_tests(self, *args, **kwargs):
            return SimpleNamespace(
                features=[],
                total_scenarios=1,
                passed_scenarios=0,
                failed_scenarios=1,
                total_cost=0,
                total_llm_calls=0,
                total_iterations=0,
                unique_tools_used=[],
            )

        def cleanup(self):
            return None

    monkeypatch.setattr("tactus.testing.test_runner.TactusTestRunner", FakeRunner)

    path = tmp_path / "sample.tac"
    path.write_text("content")

    result = cli_runner.invoke(cli_app.app, ["test", str(path)])
    assert result.exit_code == 1


def test_cli_test_command_runs_evaluation_with_scenario(monkeypatch, tmp_path, cli_runner):
    monkeypatch.setattr(cli_app, "setup_logging", lambda verbose: None)

    class FakeConfigManager:
        def load_cascade(self, path):
            return {}

    monkeypatch.setattr("tactus.core.config_manager.ConfigManager", lambda: FakeConfigManager())

    registry = SimpleNamespace(gherkin_specifications="Feature: A\nScenario: B", custom_steps={})
    result = SimpleNamespace(valid=True, registry=registry, errors=[])
    monkeypatch.setattr("tactus.validation.TactusValidator", lambda: FakeValidator(result))

    class FakeEvalRunner:
        def __init__(self, *args, **kwargs):
            pass

        def setup(self, *args, **kwargs):
            return None

        def evaluate_scenario(self, _scenario, _runs, _parallel):
            return SimpleNamespace(
                scenario_name="demo",
                success_rate=1.0,
                passed_runs=1,
                total_runs=1,
                mean_duration=0.1,
                stddev_duration=0.0,
                consistency_score=1.0,
                is_flaky=False,
            )

        def evaluate_all(self, _runs, _parallel):
            raise AssertionError("evaluate_all should not be called")

        def cleanup(self):
            return None

    monkeypatch.setattr("tactus.testing.evaluation_runner.TactusEvaluationRunner", FakeEvalRunner)

    path = tmp_path / "sample.tac"
    path.write_text("content")

    result = cli_runner.invoke(
        cli_app.app, ["test", str(path), "--runs", "2", "--scenario", "demo"]
    )
    assert result.exit_code == 0


def test_display_helpers(monkeypatch):
    console = DummyConsole()
    monkeypatch.setattr(cli_app, "console", console)

    failed = DummyScenario(
        "fail", "failed", 0.5, total_cost=1.0, llm_calls=2, iterations=1, tools_used=["x"]
    )
    failed.steps.append(DummyStep("Given", "a failure", error_message="boom"))
    failed.steps.append(DummyStep("When", "another failure", error_message=None))
    failed.steps.append(DummyStep("Then", "a success", status="passed"))
    passed = DummyScenario("pass", "passed", 0.2)
    features = [DummyFeature("Feature A", [failed, passed])]

    cli_app._display_test_results(
        SimpleNamespace(
            features=features,
            total_scenarios=2,
            passed_scenarios=1,
            failed_scenarios=1,
            total_cost=1.0,
            total_llm_calls=2,
            total_iterations=1,
            unique_tools_used=["x"],
            total_tokens=42,
        )
    )

    cli_app._display_evaluation_results([DummyEvalResult("scenario")])


def test_display_eval_results_multirun(monkeypatch):
    console = DummyConsole()
    monkeypatch.setattr(cli_app, "console", console)

    class DummyAssertion:
        def __init__(self, value, reason=None):
            self.value = value
            self.reason = reason

    long_text = "x" * 240
    report = SimpleNamespace(
        cases=[
            SimpleNamespace(
                name="task_run1",
                inputs={"x": 1},
                output={"a": "b"},
                assertions={"eval1": DummyAssertion(True, reason="first\n\nsecond\nthird\nfourth")},
            ),
            SimpleNamespace(
                name="task_run2",
                inputs={"x": 2},
                output=long_text,
                assertions={"eval1": DummyAssertion(False)},
            ),
            SimpleNamespace(
                name="task_run3",
                inputs={"x": 3},
                output="ok",
                assertions={"eval1": DummyAssertion(True)},
            ),
            SimpleNamespace(
                name="task",
                inputs={"x": 4},
                output="ok",
                assertions={"eval1": DummyAssertion(True)},
            ),
        ]
    )

    cli_app._display_eval_results(report, runs=2, console=console)

    assert any("Evaluation Results by Task" in line for line in console.lines)


def test_display_eval_results_single_run(monkeypatch):
    console = DummyConsole()
    monkeypatch.setattr(cli_app, "console", console)

    called = {}

    def fake_print(**_kwargs):
        called["printed"] = True

    report = SimpleNamespace(cases=[], print=fake_print)

    cli_app._display_eval_results(report, runs=1, console=console)

    assert called.get("printed") is True


def test_cli_eval_command_requires_evaluations(monkeypatch, tmp_path, cli_runner):
    monkeypatch.setattr(cli_app, "setup_logging", lambda verbose: None)
    monkeypatch.setattr(cli_app, "load_tactus_config", lambda: None)

    registry = SimpleNamespace(pydantic_evaluations=None)
    result = SimpleNamespace(valid=True, registry=registry, errors=[])
    monkeypatch.setattr("tactus.validation.TactusValidator", lambda: FakeValidator(result))

    path = tmp_path / "eval.tac"
    path.write_text("content")

    result = cli_runner.invoke(cli_app.app, ["eval", str(path)])
    assert result.exit_code == 1
    assert "no evaluations" in result.stdout.lower()


def test_cli_eval_command_missing_file(cli_runner):
    result = cli_runner.invoke(cli_app.app, ["eval", "missing.tac"])
    assert result.exit_code == 1


def test_cli_eval_command_validation_failure(monkeypatch, tmp_path, cli_runner):
    monkeypatch.setattr(cli_app, "setup_logging", lambda verbose: None)
    monkeypatch.setattr(cli_app, "load_tactus_config", lambda: None)

    result = SimpleNamespace(valid=False, registry=None, errors=[SimpleNamespace(message="bad")])
    monkeypatch.setattr("tactus.validation.TactusValidator", lambda: FakeValidator(result))

    path = tmp_path / "eval.tac"
    path.write_text("content")

    result = cli_runner.invoke(cli_app.app, ["eval", str(path)])
    assert result.exit_code == 1
    assert "validation failed" in result.stdout.lower()


def test_cli_eval_command_runs(monkeypatch, tmp_path, cli_runner):
    monkeypatch.setattr(cli_app, "setup_logging", lambda verbose: None)
    monkeypatch.setattr(cli_app, "load_tactus_config", lambda: None)

    registry = SimpleNamespace(
        pydantic_evaluations={
            "dataset": [{"name": "case", "inputs": {"x": 1}}],
            "evaluators": [{"type": "contains", "field": "output", "value": "ok"}],
            "thresholds": {"min_success_rate": 0.5},
        }
    )
    result = SimpleNamespace(valid=True, registry=registry, errors=[])
    monkeypatch.setattr("tactus.validation.TactusValidator", lambda: FakeValidator(result))

    class FakeRunner:
        def __init__(self, *args, **kwargs):
            pass

        def run_evaluation(self):
            report = SimpleNamespace(
                cases=[
                    SimpleNamespace(
                        name="case_run1",
                        inputs={"x": 1},
                        output={"y": 2},
                        assertions={"a": SimpleNamespace(value=True)},
                    )
                ]
            )
            return report

        def check_thresholds(self, _report):
            return True, []

    monkeypatch.setattr("tactus.testing.pydantic_eval_runner.TactusPydanticEvalRunner", FakeRunner)
    console = DummyConsole()
    monkeypatch.setattr(cli_app, "console", console)

    path = tmp_path / "eval.tac"
    path.write_text("content")

    result = cli_runner.invoke(cli_app.app, ["eval", str(path), "--runs", "2"])
    assert result.exit_code == 0


def test_cli_eval_command_warns_without_openai_key(monkeypatch, tmp_path, cli_runner):
    monkeypatch.setattr(cli_app, "setup_logging", lambda verbose: None)
    monkeypatch.setattr(cli_app, "load_tactus_config", lambda: None)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    registry = SimpleNamespace(
        pydantic_evaluations={
            "dataset": [{"name": "case", "inputs": {"x": 1}}],
            "evaluators": [{"type": "contains", "field": "output", "value": "ok"}],
        }
    )
    result = SimpleNamespace(valid=True, registry=registry, errors=[])
    monkeypatch.setattr("tactus.validation.TactusValidator", lambda: FakeValidator(result))

    class FakeRunner:
        def __init__(self, *args, **kwargs):
            pass

        def run_evaluation(self):
            return SimpleNamespace(cases=[], print=lambda **_kwargs: None)

        def check_thresholds(self, _report):
            return True, []

    monkeypatch.setattr("tactus.testing.pydantic_eval_runner.TactusPydanticEvalRunner", FakeRunner)
    console = DummyConsole()
    monkeypatch.setattr(cli_app, "console", console)

    path = tmp_path / "eval.tac"
    path.write_text("content")

    result = cli_runner.invoke(cli_app.app, ["eval", str(path)])
    assert result.exit_code == 0
    assert any("openai_api_key" in line.lower() for line in console.lines)


def test_cli_eval_command_threshold_failure(monkeypatch, tmp_path, cli_runner):
    monkeypatch.setattr(cli_app, "setup_logging", lambda verbose: None)
    monkeypatch.setattr(cli_app, "load_tactus_config", lambda: None)

    registry = SimpleNamespace(
        pydantic_evaluations={
            "dataset": [{"name": "case", "inputs": {"x": 1}}],
            "evaluators": [{"type": "contains", "field": "output", "value": "ok"}],
        }
    )
    result = SimpleNamespace(valid=True, registry=registry, errors=[])
    monkeypatch.setattr("tactus.validation.TactusValidator", lambda: FakeValidator(result))

    class FakeRunner:
        def __init__(self, *args, **kwargs):
            pass

        def run_evaluation(self):
            case = SimpleNamespace(
                name="case_run1",
                assertions={"eval": SimpleNamespace(value=True)},
                inputs={"x": 1},
                output={"y": 2},
            )
            return SimpleNamespace(cases=[case])

        def check_thresholds(self, _report):
            return False, ["too low"]

    monkeypatch.setattr("tactus.testing.pydantic_eval_runner.TactusPydanticEvalRunner", FakeRunner)
    monkeypatch.setattr(cli_app, "console", DummyConsole())

    path = tmp_path / "eval.tac"
    path.write_text("content")

    result = cli_runner.invoke(cli_app.app, ["eval", str(path)])
    assert result.exit_code == 1


def test_cli_eval_command_threshold_failure_with_config(monkeypatch, tmp_path, cli_runner):
    monkeypatch.setattr(cli_app, "setup_logging", lambda verbose: None)
    monkeypatch.setattr(cli_app, "load_tactus_config", lambda: None)

    registry = SimpleNamespace(
        pydantic_evaluations={
            "dataset": [{"name": "case", "inputs": {"x": 1}}],
            "evaluators": [{"type": "contains", "field": "output", "value": "ok"}],
            "thresholds": {"min_success_rate": 0.5},
        }
    )
    result = SimpleNamespace(valid=True, registry=registry, errors=[])
    monkeypatch.setattr("tactus.validation.TactusValidator", lambda: FakeValidator(result))

    class FakeRunner:
        def __init__(self, *args, **kwargs):
            pass

        def run_evaluation(self):
            return SimpleNamespace(cases=[])

        def check_thresholds(self, _report):
            return False, ["too low"]

    monkeypatch.setattr("tactus.testing.pydantic_eval_runner.TactusPydanticEvalRunner", FakeRunner)
    console = DummyConsole()
    monkeypatch.setattr(cli_app, "console", console)

    path = tmp_path / "eval.tac"
    path.write_text("content")

    result = cli_runner.invoke(cli_app.app, ["eval", str(path)])
    assert result.exit_code == 1


def test_eval_direct_threshold_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(cli_app, "setup_logging", lambda verbose: None)
    monkeypatch.setattr(cli_app, "load_tactus_config", lambda: None)

    registry = SimpleNamespace(
        pydantic_evaluations={
            "dataset": [{"name": "case", "inputs": {"x": 1}}],
            "evaluators": [{"type": "contains", "field": "output", "value": "ok"}],
            "thresholds": {"min_success_rate": 0.5},
        }
    )
    result = SimpleNamespace(valid=True, registry=registry, errors=[])
    monkeypatch.setattr("tactus.validation.TactusValidator", lambda: FakeValidator(result))

    class FakeRunner:
        def __init__(self, *args, **kwargs):
            pass

        def run_evaluation(self):
            return SimpleNamespace(cases=[])

        def check_thresholds(self, _report):
            return False, ["too low"]

    monkeypatch.setattr("tactus.testing.pydantic_eval_runner.TactusPydanticEvalRunner", FakeRunner)
    monkeypatch.setattr(cli_app, "console", DummyConsole())

    path = tmp_path / "eval.tac"
    path.write_text("content")

    with pytest.raises(typer.Exit):
        cli_app.eval(path, runs=2, parallel=True, verbose=False)


def test_cli_eval_command_runner_error_verbose(monkeypatch, tmp_path, cli_runner):
    monkeypatch.setattr(cli_app, "setup_logging", lambda verbose: None)
    monkeypatch.setattr(cli_app, "load_tactus_config", lambda: None)

    registry = SimpleNamespace(
        pydantic_evaluations={
            "dataset": [{"name": "case", "inputs": {"x": 1}}],
            "evaluators": [{"type": "contains", "field": "output", "value": "ok"}],
        }
    )
    result = SimpleNamespace(valid=True, registry=registry, errors=[])
    monkeypatch.setattr("tactus.validation.TactusValidator", lambda: FakeValidator(result))

    class FakeRunner:
        def __init__(self, *args, **kwargs):
            pass

        def run_evaluation(self):
            raise RuntimeError("boom")

        def check_thresholds(self, _report):
            return True, []

    monkeypatch.setattr("tactus.testing.pydantic_eval_runner.TactusPydanticEvalRunner", FakeRunner)
    monkeypatch.setattr(cli_app.console, "print_exception", lambda *_args, **_kwargs: None)

    path = tmp_path / "eval.tac"
    path.write_text("content")

    result = cli_runner.invoke(cli_app.app, ["eval", str(path), "--verbose"])
    assert result.exit_code == 1


def test_cli_eval_command_import_error(monkeypatch, tmp_path, cli_runner):
    import builtins

    monkeypatch.setattr(cli_app, "setup_logging", lambda verbose: None)
    monkeypatch.setattr(cli_app, "load_tactus_config", lambda: None)

    registry = SimpleNamespace(pydantic_evaluations={"dataset": [], "evaluators": []})
    result = SimpleNamespace(valid=True, registry=registry, errors=[])
    monkeypatch.setattr("tactus.validation.TactusValidator", lambda: FakeValidator(result))

    original_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "tactus.testing.pydantic_eval_runner":
            raise ImportError("missing")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    path = tmp_path / "eval.tac"
    path.write_text("content")

    result = cli_runner.invoke(cli_app.app, ["eval", str(path)])
    assert result.exit_code == 1


def test_display_pydantic_eval_results(monkeypatch):
    console = DummyConsole()
    monkeypatch.setattr(cli_app, "console", console)

    cli_app._display_pydantic_eval_results(SimpleNamespace(cases=[]))

    report = SimpleNamespace(
        cases=[
            SimpleNamespace(
                name="case",
                assertions={"a": True},
                scores={"score": 0.5},
                labels={"label": "ok"},
                task_duration=1.0,
            )
        ],
    )
    cli_app._display_pydantic_eval_results(report)

    report = SimpleNamespace(
        cases=[
            SimpleNamespace(
                name="case",
                assertions={"a": True},
                scores={"score": 1.0},
                labels={},
                task_duration=2.0,
            ),
            SimpleNamespace(
                name="case2",
                assertions={"a": False},
                scores={"score": 3.0},
                labels={},
                task_duration=4.0,
            ),
        ]
    )
    cli_app._display_pydantic_eval_results(report)

    report = SimpleNamespace(
        cases=[
            SimpleNamespace(
                name="case3",
                assertions={},
                scores={"score": 2.0},
                labels=None,
                task_duration=1.5,
            )
        ]
    )
    cli_app._display_pydantic_eval_results(report)
