from types import SimpleNamespace

from tactus.ide import server as ide_server


class FakeParsedFeature:
    def __init__(self, scenarios):
        self.scenarios = scenarios


class FakeParser:
    def parse(self, _specs):
        return FakeParsedFeature([SimpleNamespace(name="Scenario A")])


class FakeScenario:
    def __init__(self):
        self.name = "Scenario A"
        self.status = "passed"
        self.duration = 1.2
        self.total_cost = 0.0
        self.total_tokens = 0
        self.llm_calls = 0
        self.iterations = 1
        self.tools_used = []
        self.steps = [
            SimpleNamespace(
                keyword="Given",
                message="a precondition",
                status="passed",
                error_message=None,
            )
        ]


class FakeFeature:
    def __init__(self):
        self.name = "Feature A"
        self.scenarios = [FakeScenario()]


class FakeTestResult:
    def __init__(self):
        self.features = [FakeFeature()]
        self.total_scenarios = 1
        self.passed_scenarios = 1
        self.failed_scenarios = 0
        self.total_cost = 0.0
        self.total_tokens = 0
        self.total_llm_calls = 0
        self.total_iterations = 1
        self.unique_tools_used = []


class FakeTestRunner:
    def __init__(self, *_args, **_kwargs):
        self.setup_called = False
        self.cleaned = False

    def setup(self, _specs):
        self.setup_called = True

    def run_tests(self, parallel=False):
        return FakeTestResult()

    def cleanup(self):
        self.cleaned = True


class FakeEvalResult:
    def __init__(self):
        self.scenario_name = "Scenario A"
        self.total_runs = 2
        self.successful_runs = 2
        self.failed_runs = 0
        self.success_rate = 1.0
        self.consistency_score = 1.0
        self.is_flaky = False
        self.avg_duration = 0.5
        self.std_duration = 0.1


class FakeEvaluationRunner:
    def __init__(self, *_args, **_kwargs):
        self.cleaned = False

    def setup(self, _specs):
        return None

    def evaluate_all(self, runs=1, parallel=True):
        return [FakeEvalResult()]

    def cleanup(self):
        self.cleaned = True


def _fake_validator():
    registry = SimpleNamespace(
        gherkin_specifications="Feature: Demo\n  Scenario: A\n    Given noop",
        mocks={"tool": {"output": {"ok": True}}},
    )
    return SimpleNamespace(valid=True, errors=[], registry=registry)


def test_test_stream_success(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    file_path = workspace / "sample.tac"
    file_path.write_text("content")

    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", str(workspace))
    monkeypatch.setattr(
        "tactus.validation.TactusValidator",
        lambda: SimpleNamespace(validate_file=lambda _path: _fake_validator()),
    )
    monkeypatch.setattr("tactus.testing.TactusTestRunner", FakeTestRunner)
    monkeypatch.setattr("tactus.testing.GherkinParser", FakeParser)

    app = ide_server.create_app(initial_workspace=str(workspace))
    client = app.test_client()

    response = client.get("/api/test/stream", query_string={"path": "sample.tac"})
    data = response.data.decode("utf-8")

    assert '"event_type": "test_started"' in data
    assert '"event_type": "test_completed"' in data
    assert '"scenario_name": "Scenario A"' in data


def test_test_stream_success_with_raw_mock(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    file_path = workspace / "sample.tac"
    file_path.write_text("content")

    registry = SimpleNamespace(
        gherkin_specifications="Feature: Demo\n  Scenario: A\n    Given noop",
        mocks={"tool": {"output": {"ok": True}}, "raw": "value"},
    )
    result = SimpleNamespace(valid=True, errors=[], registry=registry)

    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", str(workspace))
    monkeypatch.setattr(
        "tactus.validation.TactusValidator",
        lambda: SimpleNamespace(validate_file=lambda _path: result),
    )
    monkeypatch.setattr("tactus.testing.TactusTestRunner", FakeTestRunner)
    monkeypatch.setattr("tactus.testing.GherkinParser", FakeParser)

    app = ide_server.create_app(initial_workspace=str(workspace))
    client = app.test_client()

    response = client.get("/api/test/stream", query_string={"path": "sample.tac"})
    data = response.data.decode("utf-8")

    assert '"event_type": "test_started"' in data


def test_test_stream_mock_disabled(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    file_path = workspace / "sample.tac"
    file_path.write_text("content")

    captured = {}

    class CapturingRunner(FakeTestRunner):
        def __init__(self, *_args, **kwargs):
            super().__init__()
            captured["mock_tools"] = kwargs.get("mock_tools")
            captured["mocked"] = kwargs.get("mocked")

    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", str(workspace))
    monkeypatch.setattr(
        "tactus.validation.TactusValidator",
        lambda: SimpleNamespace(validate_file=lambda _path: _fake_validator()),
    )
    monkeypatch.setattr("tactus.testing.TactusTestRunner", CapturingRunner)
    monkeypatch.setattr("tactus.testing.GherkinParser", FakeParser)

    app = ide_server.create_app(initial_workspace=str(workspace))
    client = app.test_client()

    response = client.get("/api/test/stream", query_string={"path": "sample.tac", "mock": "false"})
    assert response.status_code == 200
    assert captured["mock_tools"] is None
    assert captured["mocked"] is False


def test_test_stream_mock_enabled_without_registry_mocks(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    file_path = workspace / "sample.tac"
    file_path.write_text("content")

    registry = SimpleNamespace(
        gherkin_specifications="Feature: Demo\n  Scenario: A\n    Given noop", mocks={}
    )
    result = SimpleNamespace(valid=True, errors=[], registry=registry)

    captured = {}

    class CapturingRunner(FakeTestRunner):
        def __init__(self, *_args, **kwargs):
            super().__init__()
            captured["mock_tools"] = kwargs.get("mock_tools")
            captured["mocked"] = kwargs.get("mocked")

    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", str(workspace))
    monkeypatch.setattr(
        "tactus.validation.TactusValidator",
        lambda: SimpleNamespace(validate_file=lambda _path: result),
    )
    monkeypatch.setattr("tactus.testing.TactusTestRunner", CapturingRunner)
    monkeypatch.setattr("tactus.testing.GherkinParser", FakeParser)

    app = ide_server.create_app(initial_workspace=str(workspace))
    client = app.test_client()

    response = client.get("/api/test/stream", query_string={"path": "sample.tac"})
    assert response.status_code == 200
    assert captured["mock_tools"] == {"done": {"status": "ok"}}
    assert captured["mocked"] is True


def test_evaluate_stream_success(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    file_path = workspace / "sample.tac"
    file_path.write_text("content")

    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", str(workspace))
    monkeypatch.setattr(
        "tactus.validation.TactusValidator",
        lambda: SimpleNamespace(validate_file=lambda _path: _fake_validator()),
    )
    monkeypatch.setattr("tactus.testing.TactusEvaluationRunner", FakeEvaluationRunner)
    monkeypatch.setattr("tactus.testing.GherkinParser", FakeParser)

    app = ide_server.create_app(initial_workspace=str(workspace))
    client = app.test_client()

    response = client.get("/api/evaluate/stream", query_string={"path": "sample.tac"})
    data = response.data.decode("utf-8")

    assert '"event_type": "evaluation_started"' in data
    assert '"event_type": "evaluation_completed"' in data
    assert '"scenario_name": "Scenario A"' in data


def test_pydantic_eval_stream_success(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    file_path = workspace / "eval.tac"
    file_path.write_text("content")

    class FakeCase:
        def __init__(self):
            self.name = "case-1"
            self.inputs = {"x": [1, 2]}
            self.output = {"y": "ok"}
            self.assertions = SimpleNamespace(foo="bar")
            self.scores = {"score": 1.0}
            self.labels = object()
            self.task_duration = 0.12

    class FakeReport:
        def __init__(self):
            self.cases = [FakeCase()]

    class FakeRunner:
        def __init__(self, **_kwargs):
            pass

        def run_evaluation(self):
            return FakeReport()

        def check_thresholds(self, _report):
            return False, ["violation"]

    class EvalCase:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class EvaluatorConfig:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class EvaluationConfig:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class EvaluationThresholds:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    registry = SimpleNamespace(
        pydantic_evaluations={
            "dataset": [{"name": "case-1", "inputs": {"x": 1}}],
            "evaluators": [{"name": "eval", "criteria": "ok"}],
            "runs": 2,
            "thresholds": {"min_success_rate": 1.0},
        }
    )

    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", str(workspace))
    monkeypatch.setattr(
        "tactus.validation.TactusValidator",
        lambda: SimpleNamespace(
            validate_file=lambda _path: SimpleNamespace(valid=True, errors=[], registry=registry)
        ),
    )
    monkeypatch.setattr(
        ide_server,
        "TactusValidator",
        lambda: SimpleNamespace(
            validate_file=lambda _path: SimpleNamespace(valid=True, errors=[], registry=registry)
        ),
    )
    monkeypatch.setattr("tactus.testing.pydantic_eval_runner.TactusPydanticEvalRunner", FakeRunner)
    monkeypatch.setattr("tactus.testing.eval_models.EvaluationConfig", EvaluationConfig)
    monkeypatch.setattr("tactus.testing.eval_models.EvalCase", EvalCase)
    monkeypatch.setattr("tactus.testing.eval_models.EvaluatorConfig", EvaluatorConfig)
    monkeypatch.setattr("tactus.testing.eval_models.EvaluationThresholds", EvaluationThresholds)

    app = ide_server.create_app(initial_workspace=str(workspace))
    client = app.test_client()

    response = client.get("/api/pydantic-eval/stream", query_string={"path": "eval.tac"})
    data = response.data.decode("utf-8")

    assert '"type": "pydantic_eval"' in data
    assert '"lifecycle_stage": "complete"' in data


def test_pydantic_eval_stream_cases_and_thresholds(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    file_path = workspace / "eval.tac"
    file_path.write_text("content")

    class Weird:
        def __init__(self):
            self.value = 1

    class FakeCase:
        def __init__(self):
            self.name = "case-1"
            self.inputs = {"x": [1, 2]}
            self.output = ["ok"]
            self.assertions = {"a": True}
            self.scores = {"score": 1.0}
            self.labels = Weird()
            self.task_duration = 0.12

    class FakeReport:
        def __init__(self):
            self.cases = [FakeCase()]

    class FakeRunner:
        def __init__(self, **_kwargs):
            pass

        def run_evaluation(self):
            return FakeReport()

        def check_thresholds(self, _report):
            return False, ["score"]

    class EvalCase:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class EvaluatorConfig:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class EvaluationConfig:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    registry = SimpleNamespace(pydantic_evaluations={"dataset": [], "evaluators": []})

    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", str(workspace))
    monkeypatch.setattr(
        ide_server,
        "TactusValidator",
        lambda: SimpleNamespace(
            validate_file=lambda _path: SimpleNamespace(valid=True, errors=[], registry=registry)
        ),
    )
    monkeypatch.setattr("tactus.testing.pydantic_eval_runner.TactusPydanticEvalRunner", FakeRunner)
    monkeypatch.setattr("tactus.testing.eval_models.EvaluationConfig", EvaluationConfig)
    monkeypatch.setattr("tactus.testing.eval_models.EvalCase", EvalCase)
    monkeypatch.setattr("tactus.testing.eval_models.EvaluatorConfig", EvaluatorConfig)

    app = ide_server.create_app(initial_workspace=str(workspace))
    client = app.test_client()

    response = client.get("/api/pydantic-eval/stream", query_string={"path": "eval.tac"})
    data = response.data.decode("utf-8")

    assert '"thresholds_passed": false' in data


def test_pydantic_eval_stream_report_without_cases(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    file_path = workspace / "eval.tac"
    file_path.write_text("content")

    class FakeReport:
        pass

    class FakeRunner:
        def __init__(self, **_kwargs):
            pass

        def run_evaluation(self):
            return FakeReport()

        def check_thresholds(self, _report):
            return True, []

    class EvalCase:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class EvaluatorConfig:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class EvaluationConfig:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    registry = SimpleNamespace(pydantic_evaluations={"dataset": [], "evaluators": []})

    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", str(workspace))
    monkeypatch.setattr(
        ide_server,
        "TactusValidator",
        lambda: SimpleNamespace(
            validate_file=lambda _path: SimpleNamespace(valid=True, errors=[], registry=registry)
        ),
    )
    monkeypatch.setattr("tactus.testing.pydantic_eval_runner.TactusPydanticEvalRunner", FakeRunner)
    monkeypatch.setattr("tactus.testing.eval_models.EvaluationConfig", EvaluationConfig)
    monkeypatch.setattr("tactus.testing.eval_models.EvalCase", EvalCase)
    monkeypatch.setattr("tactus.testing.eval_models.EvaluatorConfig", EvaluatorConfig)

    app = ide_server.create_app(initial_workspace=str(workspace))
    client = app.test_client()

    response = client.get("/api/pydantic-eval/stream", query_string={"path": "eval.tac"})
    data = response.data.decode("utf-8")

    assert '"total_cases": 0' in data
