from types import SimpleNamespace

from rich.console import Console

from tactus.cli import app as cli_app


def test_display_test_results_handles_metrics(monkeypatch):
    console = Console(record=True)
    monkeypatch.setattr(cli_app, "console", console)

    step = SimpleNamespace(status="failed", keyword="Given", message="broken", error_message="err")
    scenario = SimpleNamespace(
        name="scenario",
        status="failed",
        duration=1.2,
        total_cost=0.01,
        llm_calls=2,
        iterations=1,
        tools_used=["tool"],
        steps=[step],
    )
    feature = SimpleNamespace(name="feature", scenarios=[scenario])
    test_result = SimpleNamespace(
        features=[feature],
        total_scenarios=1,
        passed_scenarios=0,
        failed_scenarios=1,
        total_cost=0.02,
        total_llm_calls=2,
        total_iterations=1,
        total_tokens=10,
        unique_tools_used=["tool"],
    )

    cli_app._display_test_results(test_result)

    assert "Feature" in console.export_text()


def test_display_test_results_passed_without_metrics(monkeypatch):
    console = Console(record=True)
    monkeypatch.setattr(cli_app, "console", console)

    scenario = SimpleNamespace(
        name="scenario",
        status="passed",
        duration=0.5,
        total_cost=0.0,
        llm_calls=0,
        iterations=0,
        tools_used=[],
        steps=[],
    )
    feature = SimpleNamespace(name="feature", scenarios=[scenario])
    test_result = SimpleNamespace(
        features=[feature],
        total_scenarios=1,
        passed_scenarios=1,
        failed_scenarios=0,
        total_cost=0,
        total_llm_calls=0,
        total_iterations=0,
        total_tokens=0,
        unique_tools_used=[],
    )

    cli_app._display_test_results(test_result)

    assert "scenarios" in console.export_text()


def test_display_test_results_metrics_without_cost(monkeypatch):
    console = Console(record=True)
    monkeypatch.setattr(cli_app, "console", console)

    scenario = SimpleNamespace(
        name="scenario",
        status="passed",
        duration=0.5,
        total_cost=0.0,
        llm_calls=0,
        iterations=0,
        tools_used=[],
        steps=[],
    )
    feature = SimpleNamespace(name="feature", scenarios=[scenario])
    test_result = SimpleNamespace(
        features=[feature],
        total_scenarios=1,
        passed_scenarios=1,
        failed_scenarios=0,
        total_cost=0,
        total_llm_calls=2,
        total_iterations=0,
        total_tokens=10,
        unique_tools_used=[],
    )

    cli_app._display_test_results(test_result)

    assert "Execution Metrics" in console.export_text()


def test_display_test_results_metrics_without_llm_calls(monkeypatch):
    console = Console(record=True)
    monkeypatch.setattr(cli_app, "console", console)

    scenario = SimpleNamespace(
        name="scenario",
        status="passed",
        duration=0.5,
        total_cost=0.0,
        llm_calls=0,
        iterations=0,
        tools_used=[],
        steps=[],
    )
    feature = SimpleNamespace(name="feature", scenarios=[scenario])
    test_result = SimpleNamespace(
        features=[feature],
        total_scenarios=1,
        passed_scenarios=1,
        failed_scenarios=0,
        total_cost=0.01,
        total_llm_calls=0,
        total_iterations=0,
        total_tokens=10,
        unique_tools_used=[],
    )

    cli_app._display_test_results(test_result)

    assert "Execution Metrics" in console.export_text()


def test_display_evaluation_results_outputs_summary(monkeypatch):
    console = Console(record=True)
    monkeypatch.setattr(cli_app, "console", console)

    eval_result = SimpleNamespace(
        scenario_name="scenario",
        success_rate=0.95,
        passed_runs=19,
        total_runs=20,
        mean_duration=1.0,
        stddev_duration=0.1,
        consistency_score=0.9,
        is_flaky=True,
    )

    cli_app._display_evaluation_results([eval_result])

    assert "Scenario" in console.export_text()


def test_display_eval_results_handles_multiple_runs(monkeypatch):
    console = Console(record=True)
    monkeypatch.setattr(cli_app, "console", console)

    case = SimpleNamespace(
        name="task_run1",
        assertions={"eval": SimpleNamespace(value=True)},
        inputs={"q": "hi"},
        output={"answer": "ok"},
    )
    report = SimpleNamespace(cases=[case])

    cli_app._display_eval_results(report, runs=2, console=console)

    assert "Evaluation Results by Task" in console.export_text()


def test_display_eval_results_handles_long_output_and_reasons(monkeypatch):
    console = Console(record=True)
    monkeypatch.setattr(cli_app, "console", console)

    long_text = "x" * 250
    case1 = SimpleNamespace(
        name="task_run1",
        assertions={"eval": SimpleNamespace(value=False, reason="line1\nline2\nline3\nline4")},
        inputs={"q": "hi"},
        output={"answer": long_text},
    )
    case2 = SimpleNamespace(
        name="task_run2",
        assertions={"eval": SimpleNamespace(value=True, reason=None)},
        inputs={"q": "hi"},
        output=long_text,
    )
    report = SimpleNamespace(cases=[case1, case2])

    cli_app._display_eval_results(report, runs=2, console=console)

    assert "Sample Runs" in console.export_text()


def test_display_eval_results_reason_single_line(monkeypatch):
    console = Console(record=True)
    monkeypatch.setattr(cli_app, "console", console)

    case = SimpleNamespace(
        name="task_run1",
        assertions={"eval": SimpleNamespace(value=False, reason="just one line")},
        inputs={"q": "hi"},
        output={"answer": "ok"},
    )
    report = SimpleNamespace(cases=[case])

    cli_app._display_eval_results(report, runs=2, console=console)

    assert "Evaluators" in console.export_text()


def test_display_eval_results_reason_with_empty_lines(monkeypatch):
    console = Console(record=True)
    monkeypatch.setattr(cli_app, "console", console)

    class WeirdReason:
        def __bool__(self):
            return True

        def split(self, _sep):
            return []

    case = SimpleNamespace(
        name="task_run1",
        assertions={"eval": SimpleNamespace(value=False, reason=WeirdReason())},
        inputs={"q": "hi"},
        output={"answer": "ok"},
    )
    report = SimpleNamespace(cases=[case])

    cli_app._display_eval_results(report, runs=2, console=console)

    assert "Evaluators" in console.export_text()


def test_display_eval_results_single_run_uses_report_print(monkeypatch):
    console = Console(record=True)
    monkeypatch.setattr(cli_app, "console", console)

    called = {"printed": False}

    def fake_print(**_kwargs):
        called["printed"] = True

    report = SimpleNamespace(cases=[], print=fake_print)

    cli_app._display_eval_results(report, runs=1, console=console)

    assert called["printed"] is True


def test_display_pydantic_eval_results_handles_cases(monkeypatch):
    console = Console(record=True)
    monkeypatch.setattr(cli_app, "console", console)

    case = SimpleNamespace(
        name="case",
        assertions={"accuracy": True},
        scores={"score": 0.9},
        labels={"label": "yes"},
        task_duration=0.5,
    )
    report = SimpleNamespace(cases=[case])

    cli_app._display_pydantic_eval_results(report)

    assert "Evaluation Results" in console.export_text()


def test_display_pydantic_eval_results_handles_empty_cases(monkeypatch):
    console = Console(record=True)
    monkeypatch.setattr(cli_app, "console", console)

    report = SimpleNamespace(cases=[])

    cli_app._display_pydantic_eval_results(report)

    assert "No cases found" in console.export_text()


def test_display_pydantic_eval_results_handles_case_without_scores(monkeypatch):
    console = Console(record=True)
    monkeypatch.setattr(cli_app, "console", console)

    case = SimpleNamespace(
        name="case",
        assertions={"accuracy": True},
        scores={},
        labels={},
        task_duration=0.5,
    )
    report = SimpleNamespace(cases=[case])

    cli_app._display_pydantic_eval_results(report)

    assert "Assertions" in console.export_text()


def test_display_pydantic_eval_results_handles_falsey_cases(monkeypatch):
    console = Console(record=True)
    monkeypatch.setattr(cli_app, "console", console)

    class FalseyCases(list):
        def __bool__(self):
            return False

    cases = FalseyCases(
        [
            SimpleNamespace(
                name="case",
                assertions={"accuracy": True},
                scores={"score": 0.5},
                labels={"label": "maybe"},
                task_duration=0.5,
            )
        ]
    )
    report = SimpleNamespace(cases=cases)

    cli_app._display_pydantic_eval_results(report)

    assert "Cases" in console.export_text()
