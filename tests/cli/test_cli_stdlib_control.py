from types import SimpleNamespace

import pytest
import typer
from typer.testing import CliRunner

import tactus
from tactus.cli import app as cli_app


@pytest.fixture
def cli_runner():
    return CliRunner()


def test_stdlib_test_no_spec_files(monkeypatch, tmp_path, cli_runner):
    fake_root = tmp_path / "pkg"
    stdlib_path = fake_root / "stdlib" / "tac" / "tactus"
    stdlib_path.mkdir(parents=True)

    monkeypatch.setattr(tactus, "__file__", str(fake_root / "__init__.py"))

    result = cli_runner.invoke(cli_app.app, ["stdlib", "test"])
    assert result.exit_code == 0
    assert "No spec files found" in result.stdout


def test_stdlib_test_missing_module(monkeypatch, tmp_path, cli_runner):
    fake_root = tmp_path / "pkg"
    stdlib_path = fake_root / "stdlib" / "tac" / "tactus"
    stdlib_path.mkdir(parents=True)

    monkeypatch.setattr(tactus, "__file__", str(fake_root / "__init__.py"))

    result = cli_runner.invoke(cli_app.app, ["stdlib", "test", "missing"])
    assert result.exit_code == 1
    assert "Module spec not found" in result.stdout


def test_stdlib_test_reports_failures(monkeypatch, tmp_path, cli_runner):
    fake_root = tmp_path / "pkg"
    stdlib_path = fake_root / "stdlib" / "tac" / "tactus"
    stdlib_path.mkdir(parents=True)
    spec_file = stdlib_path / "demo.spec.tac"
    spec_file.write_text("content")

    monkeypatch.setattr(tactus, "__file__", str(fake_root / "__init__.py"))

    registry = SimpleNamespace(gherkin_specifications="Feature: Demo", custom_steps={})
    result = SimpleNamespace(valid=True, errors=[], registry=registry)
    monkeypatch.setattr(
        "tactus.validation.TactusValidator",
        lambda: SimpleNamespace(validate_file=lambda path: result),
    )

    class FakeRunner:
        def __init__(self, *args, **kwargs):
            pass

        def setup(self, *args, **kwargs):
            return None

        def run_tests(self, *args, **kwargs):
            failed_scenario = SimpleNamespace(
                status="failed",
                name="scenario",
                steps=[
                    SimpleNamespace(
                        status="failed",
                        keyword="Given",
                        message="a step",
                        error_message="boom",
                    ),
                    SimpleNamespace(
                        status="passed", keyword="Then", message="ok", error_message=None
                    ),
                ],
            )
            passed_scenario = SimpleNamespace(status="passed", name="other", steps=[])
            feature = SimpleNamespace(scenarios=[failed_scenario, passed_scenario])
            return SimpleNamespace(
                features=[feature],
                passed_scenarios=0,
                failed_scenarios=1,
            )

        def cleanup(self):
            return None

    monkeypatch.setattr("tactus.testing.test_runner.TactusTestRunner", FakeRunner)

    result = cli_runner.invoke(cli_app.app, ["stdlib", "test"])
    assert result.exit_code == 1
    assert "Failed modules" in result.stdout


def test_stdlib_test_validation_failure(monkeypatch, tmp_path, cli_runner):
    fake_root = tmp_path / "pkg"
    stdlib_path = fake_root / "stdlib" / "tac" / "tactus"
    stdlib_path.mkdir(parents=True)
    spec_file = stdlib_path / "demo.spec.tac"
    spec_file.write_text("content")

    monkeypatch.setattr(tactus, "__file__", str(fake_root / "__init__.py"))

    registry = SimpleNamespace(gherkin_specifications="Feature: Demo", custom_steps={})
    result = SimpleNamespace(
        valid=False, errors=[SimpleNamespace(message="bad")], registry=registry
    )
    monkeypatch.setattr(
        "tactus.validation.TactusValidator",
        lambda: SimpleNamespace(validate_file=lambda path: result),
    )

    result = cli_runner.invoke(cli_app.app, ["stdlib", "test"])
    assert result.exit_code == 1
    assert "Validation failed" in result.stdout


def test_stdlib_test_no_specs(monkeypatch, tmp_path, cli_runner):
    fake_root = tmp_path / "pkg"
    stdlib_path = fake_root / "stdlib" / "tac" / "tactus"
    stdlib_path.mkdir(parents=True)
    spec_file = stdlib_path / "demo.spec.tac"
    spec_file.write_text("content")

    monkeypatch.setattr(tactus, "__file__", str(fake_root / "__init__.py"))

    registry = SimpleNamespace(gherkin_specifications=None, custom_steps={})
    result = SimpleNamespace(valid=True, errors=[], registry=registry)
    monkeypatch.setattr(
        "tactus.validation.TactusValidator",
        lambda: SimpleNamespace(validate_file=lambda path: result),
    )

    result = cli_runner.invoke(cli_app.app, ["stdlib", "test"])
    assert result.exit_code == 0
    assert "No specifications found" in result.stdout


def test_stdlib_test_success(monkeypatch, tmp_path, cli_runner):
    fake_root = tmp_path / "pkg"
    stdlib_path = fake_root / "stdlib" / "tac" / "tactus"
    stdlib_path.mkdir(parents=True)
    spec_file = stdlib_path / "demo.spec.tac"
    spec_file.write_text("content")

    monkeypatch.setattr(tactus, "__file__", str(fake_root / "__init__.py"))

    registry = SimpleNamespace(gherkin_specifications="Feature: Demo", custom_steps={})
    result = SimpleNamespace(valid=True, errors=[], registry=registry)
    monkeypatch.setattr(
        "tactus.validation.TactusValidator",
        lambda: SimpleNamespace(validate_file=lambda path: result),
    )

    class FakeRunner:
        def __init__(self, *args, **kwargs):
            pass

        def setup(self, *args, **kwargs):
            return None

        def run_tests(self, *args, **kwargs):
            scenario = SimpleNamespace(status="passed", name="scenario", steps=[])
            feature = SimpleNamespace(scenarios=[scenario])
            return SimpleNamespace(
                features=[feature],
                passed_scenarios=1,
                failed_scenarios=0,
            )

        def cleanup(self):
            return None

    monkeypatch.setattr("tactus.testing.test_runner.TactusTestRunner", FakeRunner)

    result = cli_runner.invoke(cli_app.app, ["stdlib", "test"])
    assert result.exit_code == 0
    assert "All stdlib tests passed" in result.stdout


def test_stdlib_test_specific_module(monkeypatch, tmp_path, cli_runner):
    fake_root = tmp_path / "pkg"
    stdlib_path = fake_root / "stdlib" / "tac" / "tactus"
    stdlib_path.mkdir(parents=True)
    spec_file = stdlib_path / "demo.spec.tac"
    spec_file.write_text("content")

    monkeypatch.setattr(tactus, "__file__", str(fake_root / "__init__.py"))

    registry = SimpleNamespace(gherkin_specifications="Feature: Demo", custom_steps={})
    result = SimpleNamespace(valid=True, errors=[], registry=registry)
    monkeypatch.setattr(
        "tactus.validation.TactusValidator",
        lambda: SimpleNamespace(validate_file=lambda path: result),
    )

    class FakeRunner:
        def __init__(self, *args, **kwargs):
            pass

        def setup(self, *args, **kwargs):
            return None

        def run_tests(self, *args, **kwargs):
            scenario = SimpleNamespace(status="passed", name="scenario", steps=[])
            feature = SimpleNamespace(scenarios=[scenario])
            return SimpleNamespace(
                features=[feature],
                passed_scenarios=1,
                failed_scenarios=0,
            )

        def cleanup(self):
            return None

    monkeypatch.setattr("tactus.testing.test_runner.TactusTestRunner", FakeRunner)

    result = cli_runner.invoke(cli_app.app, ["stdlib", "test", "demo"])
    assert result.exit_code == 0


def test_stdlib_test_verbose_exception(monkeypatch, tmp_path, cli_runner):
    fake_root = tmp_path / "pkg"
    stdlib_path = fake_root / "stdlib" / "tac" / "tactus"
    stdlib_path.mkdir(parents=True)
    spec_file = stdlib_path / "demo.spec.tac"
    spec_file.write_text("content")

    monkeypatch.setattr(tactus, "__file__", str(fake_root / "__init__.py"))

    registry = SimpleNamespace(gherkin_specifications="Feature: Demo", custom_steps={})
    result = SimpleNamespace(valid=True, errors=[], registry=registry)
    monkeypatch.setattr(
        "tactus.validation.TactusValidator",
        lambda: SimpleNamespace(validate_file=lambda path: result),
    )

    class FakeRunner:
        def __init__(self, *args, **kwargs):
            pass

        def setup(self, *args, **kwargs):
            return None

        def run_tests(self, *args, **kwargs):
            raise RuntimeError("boom")

        def cleanup(self):
            return None

    monkeypatch.setattr("tactus.testing.test_runner.TactusTestRunner", FakeRunner)
    monkeypatch.setattr(cli_app.console, "print_exception", lambda *_args, **_kwargs: None)

    result = cli_runner.invoke(cli_app.app, ["stdlib", "test", "--verbose"])
    assert result.exit_code == 1


def test_stdlib_test_verbose_exception_direct(monkeypatch, tmp_path):
    fake_root = tmp_path / "pkg"
    stdlib_path = fake_root / "stdlib" / "tac" / "tactus"
    stdlib_path.mkdir(parents=True)
    spec_file = stdlib_path / "demo.spec.tac"
    spec_file.write_text("content")

    monkeypatch.setattr(tactus, "__file__", str(fake_root / "__init__.py"))

    registry = SimpleNamespace(gherkin_specifications="Feature: Demo", custom_steps={})
    result = SimpleNamespace(valid=True, errors=[], registry=registry)
    monkeypatch.setattr(
        "tactus.validation.TactusValidator",
        lambda: SimpleNamespace(validate_file=lambda path: result),
    )

    class FakeRunner:
        def __init__(self, *args, **kwargs):
            pass

        def setup(self, *args, **kwargs):
            return None

        def run_tests(self, *args, **kwargs):
            raise RuntimeError("boom")

        def cleanup(self):
            return None

    monkeypatch.setattr("tactus.testing.test_runner.TactusTestRunner", FakeRunner)
    called = {"printed": False}

    def fake_print_exception(*_args, **_kwargs):
        called["printed"] = True

    monkeypatch.setattr(cli_app.console, "print_exception", fake_print_exception)

    with pytest.raises(typer.Exit):
        cli_app.stdlib_test(module=None, verbose=True, parallel=True)

    assert called["printed"] is True


def test_stdlib_test_exception_without_verbose(monkeypatch, tmp_path):
    fake_root = tmp_path / "pkg"
    stdlib_path = fake_root / "stdlib" / "tac" / "tactus"
    stdlib_path.mkdir(parents=True)
    spec_file = stdlib_path / "demo.spec.tac"
    spec_file.write_text("content")

    monkeypatch.setattr(tactus, "__file__", str(fake_root / "__init__.py"))

    registry = SimpleNamespace(gherkin_specifications="Feature: Demo", custom_steps={})
    result = SimpleNamespace(valid=True, errors=[], registry=registry)
    monkeypatch.setattr(
        "tactus.validation.TactusValidator",
        lambda: SimpleNamespace(validate_file=lambda path: result),
    )

    class FakeRunner:
        def __init__(self, *args, **kwargs):
            pass

        def setup(self, *args, **kwargs):
            return None

        def run_tests(self, *args, **kwargs):
            raise RuntimeError("boom")

        def cleanup(self):
            return None

    monkeypatch.setattr("tactus.testing.test_runner.TactusTestRunner", FakeRunner)
    monkeypatch.setattr(cli_app.console, "print_exception", lambda *_args, **_kwargs: None)

    with pytest.raises(typer.Exit):
        cli_app.stdlib_test(module=None, verbose=False, parallel=True)


def test_stdlib_test_runner_error_verbose(monkeypatch, tmp_path, cli_runner):
    fake_root = tmp_path / "pkg"
    stdlib_path = fake_root / "stdlib" / "tac" / "tactus"
    stdlib_path.mkdir(parents=True)
    spec_file = stdlib_path / "demo.spec.tac"
    spec_file.write_text("content")

    monkeypatch.setattr(tactus, "__file__", str(fake_root / "__init__.py"))

    registry = SimpleNamespace(gherkin_specifications="Feature: Demo", custom_steps={})
    result = SimpleNamespace(valid=True, errors=[], registry=registry)
    monkeypatch.setattr(
        "tactus.validation.TactusValidator",
        lambda: SimpleNamespace(validate_file=lambda path: result),
    )

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

    result = cli_runner.invoke(cli_app.app, ["stdlib", "test", "--verbose"])
    assert result.exit_code == 1


def test_control_command_no_sockets(monkeypatch, cli_runner):
    monkeypatch.setattr("glob.glob", lambda pattern: [])

    result = cli_runner.invoke(cli_app.app, ["control"])
    assert result.exit_code == 1
    assert "No Tactus runtime sockets found" in result.stdout


def test_control_command_single_socket(monkeypatch, cli_runner):
    monkeypatch.setattr("glob.glob", lambda pattern: ["/tmp/tactus-control-1.sock"])

    captured = {}

    async def fake_main(socket_path, auto_respond):
        captured["socket_path"] = socket_path
        captured["auto_respond"] = auto_respond

    monkeypatch.setattr("tactus.cli.control.main", fake_main)

    result = cli_runner.invoke(cli_app.app, ["control"])
    assert result.exit_code == 0
    assert captured["socket_path"] == "/tmp/tactus-control-1.sock"


def test_control_command_multiple_sockets(monkeypatch, cli_runner):
    monkeypatch.setattr(
        "glob.glob",
        lambda pattern: ["/tmp/tactus-control-1.sock", "/tmp/tactus-control-2.sock"],
    )
    monkeypatch.setattr(cli_app.Prompt, "ask", lambda *_args, **_kwargs: "2")

    captured = {}

    async def fake_main(socket_path, auto_respond):
        captured["socket_path"] = socket_path
        captured["auto_respond"] = auto_respond

    monkeypatch.setattr("tactus.cli.control.main", fake_main)

    result = cli_runner.invoke(cli_app.app, ["control", "--respond", "yes"])
    assert result.exit_code == 0
    assert captured["socket_path"] == "/tmp/tactus-control-2.sock"
