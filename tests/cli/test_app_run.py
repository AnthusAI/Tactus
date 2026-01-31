import os
import sys
from pathlib import Path

import pytest
import typer

from tactus.cli import app as cli_app
from tactus.sandbox.protocol import ExecutionResult, ExecutionStatus


class DummyValidator:
    def __init__(self, registry=None, should_raise=False):
        self._registry = registry
        self._should_raise = should_raise

    def validate(self, _source, _mode):
        if self._should_raise:
            raise ValueError("invalid")
        return type("Result", (), {"registry": self._registry})()


class DummyConfigManager:
    def load_cascade(self, _workflow_file):
        return {}


class DummySandboxConfig:
    def __init__(
        self,
        should_use=False,
        explicit_disabled=True,
        error_if_unavailable=False,
        **_kwargs,
    ):
        self._should_use = should_use
        self._explicit_disabled = explicit_disabled
        self._error_if_unavailable = error_if_unavailable
        self.env = {}

    def should_use_sandbox(self, _docker_available):
        return self._should_use

    def is_explicitly_disabled(self):
        return self._explicit_disabled

    def should_error_if_unavailable(self):
        return self._error_if_unavailable


class DummyRuntime:
    next_result = None
    next_exception = None
    last_context = None

    def __init__(self, **_kwargs):
        pass

    async def execute(self, _source, _context, format="lua"):
        DummyRuntime.last_context = _context
        if DummyRuntime.next_exception:
            raise DummyRuntime.next_exception
        return DummyRuntime.next_result or {"success": True, "result": "ok"}


class DummyControlLoopHandler:
    last_channels = None

    def __init__(self, **_kwargs):
        DummyControlLoopHandler.last_channels = _kwargs.get("channels")


class DummyControlLoopHITLAdapter:
    def __init__(self, _handler):
        pass


class DummyCLIControlChannel:
    channel_id = "cli"

    def __init__(self, **_kwargs):
        pass


def _patch_runtime_dependencies(
    monkeypatch, *, sandbox_config=None, docker_available=True, validator_factory=None
):
    monkeypatch.setattr("tactus.core.config_manager.ConfigManager", lambda: DummyConfigManager())
    monkeypatch.setattr(cli_app, "TactusRuntime", DummyRuntime)
    if validator_factory is None:

        def _default_validator_factory():
            return DummyValidator()

        validator_factory = _default_validator_factory
    monkeypatch.setattr(cli_app, "TactusValidator", validator_factory)
    monkeypatch.setattr("tactus.validation.TactusValidator", validator_factory)
    monkeypatch.setattr(
        "tactus.sandbox.is_docker_available",
        lambda: (docker_available, "no-docker"),
    )
    monkeypatch.setattr(
        "tactus.sandbox.SandboxConfig",
        sandbox_config or DummySandboxConfig,
    )
    monkeypatch.setattr("tactus.adapters.channels.load_default_channels", lambda **_kwargs: [])
    monkeypatch.setattr("tactus.adapters.channels.cli.CLIControlChannel", DummyCLIControlChannel)
    monkeypatch.setattr("tactus.adapters.control_loop.ControlLoopHandler", DummyControlLoopHandler)
    monkeypatch.setattr(
        "tactus.adapters.control_loop.ControlLoopHITLAdapter",
        DummyControlLoopHITLAdapter,
    )


def test_run_missing_file(tmp_path):
    missing = tmp_path / "missing.tac"
    with pytest.raises(typer.Exit):
        cli_app.run(missing, log_level=None, log_format="rich")


def test_run_invalid_param_format(tmp_path, monkeypatch):
    workflow = tmp_path / "workflow.tac"
    workflow.write_text("print('hi')")

    _patch_runtime_dependencies(monkeypatch)

    with pytest.raises(typer.Exit):
        cli_app.run(workflow, param=["nope"], log_level=None, log_format="rich")


def test_run_unknown_storage_backend(tmp_path, monkeypatch):
    workflow = tmp_path / "workflow.tac"
    workflow.write_text("print('hi')")

    _patch_runtime_dependencies(monkeypatch)

    with pytest.raises(typer.Exit):
        cli_app.run(workflow, storage="unknown", param=None, log_level=None, log_format="rich")


def test_run_non_sandbox_success(tmp_path, monkeypatch):
    workflow = tmp_path / "workflow.tac"
    workflow.write_text("print('hi')")

    _patch_runtime_dependencies(monkeypatch)

    DummyRuntime.next_result = {
        "success": True,
        "result": "done",
        "state": {"k": "v"},
        "iterations": 2,
        "tools_used": ["done"],
    }
    DummyRuntime.next_exception = None

    cli_app.run(
        workflow,
        sandbox=False,
        storage="memory",
        param=None,
        mock_all=False,
        real_all=False,
        mock=None,
        real=None,
        log_level=None,
        log_format="rich",
    )


def test_run_waiting_for_human(tmp_path, monkeypatch):
    from tactus.core.exceptions import ProcedureWaitingForHuman

    workflow = tmp_path / "workflow.tac"
    workflow.write_text("print('hi')")

    _patch_runtime_dependencies(monkeypatch)
    monkeypatch.setattr(cli_app.console, "print", lambda *_args, **_kwargs: None)

    DummyRuntime.next_result = None
    DummyRuntime.next_exception = ProcedureWaitingForHuman("pause", pending_message_id="msg-1")

    cli_app.run(
        workflow,
        sandbox=False,
        storage="memory",
        param=None,
        mock_all=False,
        real_all=False,
        mock=None,
        real=None,
        log_level=None,
        log_format="rich",
    )


def test_run_missing_required_prompts(tmp_path, monkeypatch):
    workflow = tmp_path / "workflow.tac"
    workflow.write_text("print('hi')")

    registry = type("Registry", (), {"input_schema": {"name": {"required": True}}})()
    _patch_runtime_dependencies(
        monkeypatch,
        validator_factory=lambda: DummyValidator(registry),
    )
    monkeypatch.setattr(cli_app.console, "print", lambda *_args, **_kwargs: None)

    monkeypatch.setattr(cli_app, "_prompt_for_inputs", lambda *_args: {"name": "ok"})

    DummyRuntime.next_exception = None
    cli_app.run(
        workflow,
        sandbox=False,
        storage="memory",
        param=None,
        mock_all=False,
        real_all=False,
        mock=None,
        real=None,
        log_level=None,
        log_format="rich",
    )


def test_run_missing_required_prints_warning(tmp_path, monkeypatch):
    workflow = tmp_path / "workflow.tac"
    workflow.write_text("print('hi')")

    registry = type("Registry", (), {"input_schema": {"name": {"required": True}}})()
    _patch_runtime_dependencies(
        monkeypatch,
        validator_factory=lambda: DummyValidator(registry),
    )

    messages = []

    def fake_print(message, *args, **kwargs):
        messages.append(message)

    monkeypatch.setattr(cli_app.console, "print", fake_print)
    monkeypatch.setattr(cli_app, "_prompt_for_inputs", lambda *_args: {"name": "ok"})

    DummyRuntime.next_exception = None
    cli_app.run(
        workflow,
        sandbox=False,
        storage="memory",
        param=None,
        interactive=False,
        mock_all=False,
        real_all=False,
        mock=None,
        real=None,
        log_level=None,
        log_format="rich",
    )

    assert any("Missing required inputs" in str(msg) for msg in messages)


def test_run_prompts_for_inputs_when_interactive(tmp_path, monkeypatch):
    workflow = tmp_path / "workflow.tac"
    workflow.write_text("print('hi')")

    registry = type("Registry", (), {"input_schema": {"name": {"required": True}}})()
    _patch_runtime_dependencies(
        monkeypatch,
        validator_factory=lambda: DummyValidator(registry),
    )
    monkeypatch.setattr(cli_app.console, "print", lambda *_args, **_kwargs: None)

    prompts = {}

    def fake_prompt(_console, _schema, provided):
        prompts["called"] = True
        return {"name": provided.get("name", "ok")}

    monkeypatch.setattr(cli_app, "_prompt_for_inputs", fake_prompt)

    DummyRuntime.next_exception = None
    cli_app.run(
        workflow,
        sandbox=False,
        storage="memory",
        param=None,
        interactive=True,
        mock_all=False,
        real_all=False,
        mock=None,
        real=None,
        log_level=None,
        log_format="rich",
    )

    assert prompts.get("called") is True


def test_run_schema_validation_warning_verbose(tmp_path, monkeypatch):
    workflow = tmp_path / "workflow.tac"
    workflow.write_text("print('hi')")

    _patch_runtime_dependencies(
        monkeypatch,
        validator_factory=lambda: DummyValidator(should_raise=True),
    )

    messages = []

    def fake_print(message, *args, **kwargs):
        messages.append(message)

    monkeypatch.setattr(cli_app.console, "print", fake_print)

    DummyRuntime.next_exception = None
    cli_app.run(
        workflow,
        sandbox=False,
        storage="memory",
        param=None,
        interactive=False,
        verbose=True,
        mock_all=False,
        real_all=False,
        mock=None,
        real=None,
        log_level=None,
        log_format="rich",
    )

    assert any("Could not extract input schema" in str(msg) for msg in messages)


def test_run_schema_validation_warning_nonverbose(tmp_path, monkeypatch):
    workflow = tmp_path / "workflow.tac"
    workflow.write_text("print('hi')")

    _patch_runtime_dependencies(
        monkeypatch,
        validator_factory=lambda: DummyValidator(should_raise=True),
    )
    monkeypatch.setattr(cli_app.console, "print", lambda *_args, **_kwargs: None)

    DummyRuntime.next_exception = None
    cli_app.run(
        workflow,
        sandbox=False,
        storage="memory",
        param=None,
        interactive=False,
        verbose=False,
        mock_all=False,
        real_all=False,
        mock=None,
        real=None,
        log_level=None,
        log_format="rich",
    )


def test_run_real_all_prints_notice(tmp_path, monkeypatch):
    workflow = tmp_path / "workflow.tac"
    workflow.write_text("print('hi')")

    _patch_runtime_dependencies(monkeypatch)

    messages = []
    monkeypatch.setattr(cli_app.console, "print", lambda msg, *args, **kwargs: messages.append(msg))

    DummyRuntime.next_exception = None
    cli_app.run(
        workflow,
        sandbox=False,
        storage="memory",
        param=None,
        real_all=True,
        mock_all=False,
        mock=None,
        real=None,
        log_level=None,
        log_format="rich",
    )

    assert any("Using real implementations for all tools" in str(msg) for msg in messages)


def test_run_formats_tactus_result_output(tmp_path, monkeypatch):
    from tactus.protocols.result import TactusResult

    workflow = tmp_path / "workflow.tac"
    workflow.write_text("print('hi')")

    _patch_runtime_dependencies(monkeypatch)

    messages = []
    monkeypatch.setattr(cli_app.console, "print", lambda msg, *args, **kwargs: messages.append(msg))

    DummyRuntime.next_exception = None
    DummyRuntime.next_result = {
        "success": True,
        "result": TactusResult(output="payload"),
        "state": {"k": "v"},
        "iterations": 1,
        "tools_used": [],
    }

    cli_app.run(
        workflow,
        sandbox=False,
        storage="memory",
        param=None,
        mock_all=False,
        real_all=False,
        mock=None,
        real=None,
        log_level=None,
        log_format="rich",
    )

    assert any("payload" in str(msg) for msg in messages)


def test_run_skips_result_display_when_empty(tmp_path, monkeypatch):
    workflow = tmp_path / "workflow.tac"
    workflow.write_text("print('hi')")

    _patch_runtime_dependencies(monkeypatch)

    messages = []
    monkeypatch.setattr(cli_app.console, "print", lambda msg, *args, **kwargs: messages.append(msg))

    DummyRuntime.next_exception = None
    DummyRuntime.next_result = {
        "success": True,
        "result": None,
        "state": {},
        "iterations": 0,
        "tools_used": [],
    }

    cli_app.run(
        workflow,
        sandbox=False,
        storage="memory",
        param=None,
        mock_all=False,
        real_all=False,
        mock=None,
        real=None,
        log_level=None,
        log_format="rich",
    )

    assert not any("Result:" in str(msg) for msg in messages)


def test_run_tactus_result_import_error(tmp_path, monkeypatch):
    workflow = tmp_path / "workflow.tac"
    workflow.write_text("print('hi')")

    _patch_runtime_dependencies(monkeypatch)
    monkeypatch.setattr(cli_app.console, "print", lambda *_args, **_kwargs: None)

    DummyRuntime.next_exception = None
    DummyRuntime.next_result = {
        "success": True,
        "result": "plain",
        "state": {},
        "iterations": 0,
        "tools_used": [],
    }

    class BrokenModule:
        def __getattr__(self, _name):
            raise RuntimeError("boom")

    monkeypatch.setitem(sys.modules, "tactus.protocols.result", BrokenModule())

    cli_app.run(
        workflow,
        sandbox=False,
        storage="memory",
        param=None,
        mock_all=False,
        real_all=False,
        mock=None,
        real=None,
        log_level=None,
        log_format="rich",
    )


def test_run_mock_list_registers_tool(tmp_path, monkeypatch):
    workflow = tmp_path / "workflow.tac"
    workflow.write_text("print('hi')")

    _patch_runtime_dependencies(monkeypatch)
    monkeypatch.setattr(cli_app.console, "print", lambda *_args, **_kwargs: None)

    DummyRuntime.next_exception = None
    cli_app.run(
        workflow,
        sandbox=False,
        storage="memory",
        param=None,
        mock_all=False,
        real_all=False,
        mock=["tool_a"],
        real=None,
        log_level=None,
        log_format="rich",
    )


def test_run_sandbox_sets_openai_key(tmp_path, monkeypatch):
    workflow = tmp_path / "workflow.tac"
    workflow.write_text("print('hi')")

    class CaptureSandboxConfig(DummySandboxConfig):
        def __init__(self, **kwargs):
            super().__init__(should_use=True, explicit_disabled=False, error_if_unavailable=False)
            self.kwargs = kwargs

    class DummyRunner:
        def __init__(self, _config):
            pass

        async def run(self, **_kwargs):
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                result={"ok": True},
                metadata={"state": {}, "iterations": 1, "tools_used": []},
            )

    _patch_runtime_dependencies(monkeypatch, sandbox_config=CaptureSandboxConfig)
    monkeypatch.setattr("tactus.sandbox.ContainerRunner", DummyRunner)
    monkeypatch.setattr(cli_app.console, "print", lambda *_args, **_kwargs: None)
    monkeypatch.setenv("OPENAI_API_KEY", "")

    DummyRuntime.next_exception = None
    cli_app.run(
        workflow,
        sandbox=None,
        storage="memory",
        param=None,
        openai_api_key="test-key",
        mock_all=False,
        real_all=False,
        mock=None,
        real=None,
        log_level=None,
        log_format="rich",
    )

    assert os.environ.get("OPENAI_API_KEY") == "test-key"


def test_run_sandbox_defaults_enabled(tmp_path, monkeypatch):
    workflow = tmp_path / "workflow.tac"
    workflow.write_text("print('hi')")

    captured = {}

    class CaptureSandboxConfig(DummySandboxConfig):
        def __init__(self, **kwargs):
            captured.update(kwargs)
            super().__init__(should_use=False, explicit_disabled=False, error_if_unavailable=False)

    _patch_runtime_dependencies(monkeypatch, sandbox_config=CaptureSandboxConfig)
    monkeypatch.setattr(
        "tactus.core.config_manager.ConfigManager",
        lambda: type("Cfg", (), {"load_cascade": lambda *_args: {"sandbox": {}}})(),
    )
    monkeypatch.setattr(cli_app.console, "print", lambda *_args, **_kwargs: None)

    DummyRuntime.next_exception = None
    cli_app.run(
        workflow,
        sandbox=None,
        storage="memory",
        param=None,
        mock_all=False,
        real_all=False,
        mock=None,
        real=None,
        log_level=None,
        log_format="rich",
    )

    assert captured.get("enabled") is True


def test_run_sandbox_uses_configured_enabled_value(tmp_path, monkeypatch):
    workflow = tmp_path / "workflow.tac"
    workflow.write_text("print('hi')")

    captured = {}

    class CaptureSandboxConfig(DummySandboxConfig):
        def __init__(self, **kwargs):
            captured.update(kwargs)
            super().__init__(should_use=False, explicit_disabled=True, error_if_unavailable=False)

    _patch_runtime_dependencies(monkeypatch, sandbox_config=CaptureSandboxConfig)
    monkeypatch.setattr(
        "tactus.core.config_manager.ConfigManager",
        lambda: type("Cfg", (), {"load_cascade": lambda *_args: {"sandbox": {"enabled": False}}})(),
    )
    monkeypatch.setattr(cli_app.console, "print", lambda *_args, **_kwargs: None)

    DummyRuntime.next_exception = None
    cli_app.run(
        workflow,
        sandbox=None,
        storage="memory",
        param=None,
        mock_all=False,
        real_all=False,
        mock=None,
        real=None,
        log_level=None,
        log_format="rich",
    )

    assert captured.get("enabled") is False


def test_run_sandbox_skips_api_key_when_unset(tmp_path, monkeypatch):
    workflow = tmp_path / "workflow.tac"
    workflow.write_text("print('hi')")

    class CaptureSandboxConfig(DummySandboxConfig):
        def __init__(self, **kwargs):
            super().__init__(should_use=True, explicit_disabled=False, error_if_unavailable=False)

    class DummyRunner:
        def __init__(self, _config):
            pass

        async def run(self, **_kwargs):
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                result={"ok": True},
                metadata={"state": {}, "iterations": 1, "tools_used": []},
            )

    _patch_runtime_dependencies(monkeypatch, sandbox_config=CaptureSandboxConfig)
    monkeypatch.setattr("tactus.sandbox.ContainerRunner", DummyRunner)
    monkeypatch.setattr(cli_app.console, "print", lambda *_args, **_kwargs: None)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    DummyRuntime.next_exception = None
    cli_app.run(
        workflow,
        sandbox=None,
        storage="memory",
        param=None,
        openai_api_key=None,
        mock_all=False,
        real_all=False,
        mock=None,
        real=None,
        log_level=None,
        log_format="rich",
    )

    assert os.environ.get("OPENAI_API_KEY") is None


def test_run_docker_required_unavailable(tmp_path, monkeypatch):
    workflow = tmp_path / "workflow.tac"
    workflow.write_text("print('hi')")

    class RequiredSandboxConfig(DummySandboxConfig):
        def __init__(self, **kwargs):
            super().__init__(should_use=False, explicit_disabled=False, error_if_unavailable=True)

    _patch_runtime_dependencies(
        monkeypatch, sandbox_config=RequiredSandboxConfig, docker_available=False
    )

    with pytest.raises(typer.Exit):
        cli_app.run(workflow, sandbox=None, param=None, log_level=None, log_format="rich")


def test_run_param_parsing_with_schema_dict(tmp_path, monkeypatch):
    workflow = tmp_path / "workflow.tac"
    workflow.write_text("print('hi')")

    registry = type("Registry", (), {"input_schema": {"count": {"type": "number"}}})()
    _patch_runtime_dependencies(
        monkeypatch,
        validator_factory=lambda: DummyValidator(registry),
    )
    monkeypatch.setattr(cli_app.console, "print", lambda *_args, **_kwargs: None)

    DummyRuntime.next_exception = None
    cli_app.run(
        workflow,
        sandbox=False,
        storage="memory",
        param=["count=3.5"],
        interactive=False,
        verbose=True,
        mock_all=False,
        real_all=False,
        mock=None,
        real=None,
        log_level=None,
        log_format="rich",
    )

    assert DummyRuntime.last_context["count"] == 3.5


def test_run_param_parsing_with_schema_dict_nonverbose(tmp_path, monkeypatch):
    workflow = tmp_path / "workflow.tac"
    workflow.write_text("print('hi')")

    registry = type("Registry", (), {"input_schema": {"count": {"type": "number"}}})()
    _patch_runtime_dependencies(
        monkeypatch,
        validator_factory=lambda: DummyValidator(registry),
    )
    monkeypatch.setattr(cli_app.console, "print", lambda *_args, **_kwargs: None)

    DummyRuntime.next_exception = None
    cli_app.run(
        workflow,
        sandbox=False,
        storage="memory",
        param=["count=3.5"],
        interactive=False,
        verbose=False,
        mock_all=False,
        real_all=False,
        mock=None,
        real=None,
        log_level=None,
        log_format="rich",
    )

    assert DummyRuntime.last_context["count"] == 3.5


def test_run_extracts_input_schema_from_registry(tmp_path, monkeypatch):
    workflow = tmp_path / "workflow.tac"
    workflow.write_text("print('hi')")

    registry = type("Registry", (), {"input_schema": {"flag": {"type": "boolean"}}})()
    _patch_runtime_dependencies(
        monkeypatch,
        validator_factory=lambda: DummyValidator(registry),
    )
    monkeypatch.setattr(cli_app.console, "print", lambda *_args, **_kwargs: None)

    DummyRuntime.next_exception = None
    cli_app.run(
        workflow,
        sandbox=False,
        storage="memory",
        param=["flag=true"],
        interactive=False,
        mock_all=False,
        real_all=False,
        mock=None,
        real=None,
        log_level=None,
        log_format="rich",
    )

    assert DummyRuntime.last_context["flag"] is True


def test_run_param_parsing_schema_fallback_json(tmp_path, monkeypatch):
    workflow = tmp_path / "workflow.tac"
    workflow.write_text("print('hi')")

    registry = type("Registry", (), {"input_schema": {"meta": "string"}})()
    _patch_runtime_dependencies(
        monkeypatch,
        validator_factory=lambda: DummyValidator(registry),
    )
    monkeypatch.setattr(cli_app.console, "print", lambda *_args, **_kwargs: None)

    DummyRuntime.next_exception = None
    cli_app.run(
        workflow,
        sandbox=False,
        storage="memory",
        param=['meta={"a": 1}'],
        interactive=False,
        mock_all=False,
        real_all=False,
        mock=None,
        real=None,
        log_level=None,
        log_format="rich",
    )

    assert DummyRuntime.last_context["meta"] == {"a": 1}


def test_run_param_parsing_schema_fallback_string(tmp_path, monkeypatch):
    workflow = tmp_path / "workflow.tac"
    workflow.write_text("print('hi')")

    registry = type("Registry", (), {"input_schema": {"meta": "string"}})()
    _patch_runtime_dependencies(
        monkeypatch,
        validator_factory=lambda: DummyValidator(registry),
    )
    monkeypatch.setattr(cli_app.console, "print", lambda *_args, **_kwargs: None)

    DummyRuntime.next_exception = None
    cli_app.run(
        workflow,
        sandbox=False,
        storage="memory",
        param=["meta=nope"],
        interactive=False,
        mock_all=False,
        real_all=False,
        mock=None,
        real=None,
        log_level=None,
        log_format="rich",
    )

    assert DummyRuntime.last_context["meta"] == "nope"


def test_run_param_parsing_without_schema(tmp_path, monkeypatch):
    workflow = tmp_path / "workflow.tac"
    workflow.write_text("print('hi')")

    _patch_runtime_dependencies(monkeypatch, validator_factory=lambda: DummyValidator(None))
    monkeypatch.setattr(cli_app.console, "print", lambda *_args, **_kwargs: None)

    DummyRuntime.next_exception = None
    cli_app.run(
        workflow,
        sandbox=False,
        storage="memory",
        param=["list=[1,2]", "name=hi"],
        verbose=True,
        mock_all=False,
        real_all=False,
        mock=None,
        real=None,
        log_level=None,
        log_format="rich",
    )

    assert DummyRuntime.last_context["list"] == [1, 2]
    assert DummyRuntime.last_context["name"] == "hi"


def test_run_yaml_skips_validator(tmp_path, monkeypatch):
    workflow = tmp_path / "workflow.yaml"
    workflow.write_text("steps: []")

    class ExplodingValidator:
        def __init__(self):
            raise AssertionError("validator should not be called for yaml")

    _patch_runtime_dependencies(monkeypatch)
    monkeypatch.setattr("tactus.validation.TactusValidator", ExplodingValidator)
    monkeypatch.setattr(cli_app.console, "print", lambda *_args, **_kwargs: None)

    DummyRuntime.next_exception = None
    cli_app.run(
        workflow,
        sandbox=False,
        storage="memory",
        param=None,
        mock_all=False,
        real_all=False,
        mock=None,
        real=None,
        log_level=None,
        log_format="rich",
    )


def test_run_storage_path_file_parent_used(tmp_path, monkeypatch):
    workflow = tmp_path / "workflow.tac"
    workflow.write_text("print('hi')")
    storage_file = tmp_path / "storage.db"
    storage_file.write_text("data")

    captured = {}

    class CapturingStorage:
        def __init__(self, storage_dir):
            captured["storage_dir"] = storage_dir

    _patch_runtime_dependencies(monkeypatch)
    monkeypatch.setattr(cli_app, "FileStorage", CapturingStorage)
    monkeypatch.setattr(cli_app.console, "print", lambda *_args, **_kwargs: None)

    DummyRuntime.next_exception = None
    cli_app.run(
        workflow,
        sandbox=False,
        storage="file",
        storage_path=str(storage_file),
        param=None,
        mock_all=False,
        real_all=False,
        mock=None,
        real=None,
        log_level=None,
        log_format="rich",
    )

    assert captured["storage_dir"] == str(tmp_path)


def test_run_storage_path_dir_used(tmp_path, monkeypatch):
    workflow = tmp_path / "workflow.tac"
    workflow.write_text("print('hi')")
    storage_dir = tmp_path / "store"
    storage_dir.mkdir()

    captured = {}

    class CapturingStorage:
        def __init__(self, storage_dir):
            captured["storage_dir"] = storage_dir

    _patch_runtime_dependencies(monkeypatch)
    monkeypatch.setattr(cli_app, "FileStorage", CapturingStorage)
    monkeypatch.setattr(cli_app.console, "print", lambda *_args, **_kwargs: None)

    DummyRuntime.next_exception = None
    cli_app.run(
        workflow,
        sandbox=False,
        storage="file",
        storage_path=str(storage_dir),
        param=None,
        mock_all=False,
        real_all=False,
        mock=None,
        real=None,
        log_level=None,
        log_format="rich",
    )

    assert captured["storage_dir"] == str(storage_dir)


def test_run_sandbox_auto_notice_when_docker_missing(tmp_path, monkeypatch):
    workflow = tmp_path / "workflow.tac"
    workflow.write_text("print('hi')")

    class AutoSandboxConfig(DummySandboxConfig):
        def __init__(self, **kwargs):
            super().__init__(should_use=False, explicit_disabled=False, error_if_unavailable=False)
            self.env = {}

    _patch_runtime_dependencies(
        monkeypatch, sandbox_config=AutoSandboxConfig, docker_available=False
    )
    monkeypatch.setattr(cli_app.console, "print", lambda *_args, **_kwargs: None)

    DummyRuntime.next_exception = None
    cli_app.run(
        workflow,
        sandbox=None,
        storage="memory",
        param=None,
        mock_all=False,
        real_all=False,
        mock=None,
        real=None,
        log_level=None,
        log_format="rich",
    )


def test_run_sandbox_config_default_enabled(tmp_path, monkeypatch):
    workflow = tmp_path / "workflow.tac"
    workflow.write_text("print('hi')")

    captured = {}

    class CapturingSandboxConfig(DummySandboxConfig):
        def __init__(self, **kwargs):
            captured.update(kwargs)
            super().__init__(should_use=False, explicit_disabled=False, error_if_unavailable=False)
            self.env = {}

    class ConfigWithSandbox:
        def load_cascade(self, _workflow_file):
            return {"sandbox": {"enabled": None}}

    _patch_runtime_dependencies(monkeypatch, sandbox_config=CapturingSandboxConfig)
    monkeypatch.setattr("tactus.core.config_manager.ConfigManager", lambda: ConfigWithSandbox())
    monkeypatch.setattr(cli_app.console, "print", lambda *_args, **_kwargs: None)

    DummyRuntime.next_exception = None
    cli_app.run(
        workflow,
        sandbox=None,
        storage="memory",
        param=None,
        mock_all=False,
        real_all=False,
        mock=None,
        real=None,
        log_level=None,
        log_format="rich",
    )

    assert captured.get("enabled") is True


def test_run_file_storage_path_from_file(tmp_path, monkeypatch):
    workflow = tmp_path / "workflow.tac"
    workflow.write_text("print('hi')")

    storage_file = tmp_path / "storage" / "data.json"
    storage_file.parent.mkdir()
    storage_file.write_text("data")

    captured = {}

    class DummyFileStorage:
        def __init__(self, storage_dir):
            captured["storage_dir"] = storage_dir

    _patch_runtime_dependencies(monkeypatch)
    monkeypatch.setattr(cli_app, "FileStorage", DummyFileStorage)

    DummyRuntime.next_exception = None
    cli_app.run(
        workflow,
        sandbox=False,
        storage="file",
        storage_path=str(storage_file),
        param=None,
        mock_all=False,
        real_all=False,
        mock=None,
        real=None,
        log_level=None,
        log_format="rich",
    )

    assert captured["storage_dir"] == str(storage_file.parent)


def test_run_file_storage_default_path(tmp_path, monkeypatch):
    workflow = tmp_path / "workflow.tac"
    workflow.write_text("print('hi')")

    captured = {}

    class DummyFileStorage:
        def __init__(self, storage_dir):
            captured["storage_dir"] = storage_dir

    _patch_runtime_dependencies(monkeypatch)
    monkeypatch.setattr(cli_app, "FileStorage", DummyFileStorage)

    DummyRuntime.next_exception = None
    cli_app.run(
        workflow,
        sandbox=False,
        storage="file",
        storage_path=None,
        param=None,
        mock_all=False,
        real_all=False,
        mock=None,
        real=None,
        log_level=None,
        log_format="rich",
    )

    assert captured["storage_dir"] == str((Path.cwd() / ".tac" / "storage"))


def test_run_interactive_prompts_all_inputs(tmp_path, monkeypatch):
    workflow = tmp_path / "workflow.tac"
    workflow.write_text("print('hi')")

    registry = type("Registry", (), {"input_schema": {"name": {"required": True}}})()
    _patch_runtime_dependencies(
        monkeypatch,
        validator_factory=lambda: DummyValidator(registry),
    )
    monkeypatch.setattr(cli_app.console, "print", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cli_app, "_prompt_for_inputs", lambda *_args: {"name": "ok"})

    DummyRuntime.next_exception = None
    cli_app.run(
        workflow,
        sandbox=False,
        storage="memory",
        param=None,
        interactive=True,
        mock_all=False,
        real_all=False,
        mock=None,
        real=None,
        log_level=None,
        log_format="rich",
    )


def test_run_sets_sandbox_network_default(tmp_path, monkeypatch):
    workflow = tmp_path / "workflow.tac"
    workflow.write_text("print('hi')")

    captured = {}

    class CapturingSandboxConfig(DummySandboxConfig):
        def __init__(self, **kwargs):
            captured.update(kwargs)
            super().__init__(should_use=False, explicit_disabled=True, error_if_unavailable=False)
            self.env = {}

    _patch_runtime_dependencies(monkeypatch, sandbox_config=CapturingSandboxConfig)
    monkeypatch.setattr(cli_app.console, "print", lambda *_args, **_kwargs: None)

    DummyRuntime.next_exception = None
    cli_app.run(
        workflow,
        sandbox=None,
        sandbox_broker="tcp",
        sandbox_network=None,
        storage="memory",
        param=None,
        mock_all=False,
        real_all=False,
        mock=None,
        real=None,
        log_level=None,
        log_format="rich",
    )

    assert captured.get("network") == "bridge"


def test_run_input_schema_extract_error_verbose(tmp_path, monkeypatch):
    workflow = tmp_path / "workflow.tac"
    workflow.write_text("print('hi')")

    class ExplodingValidator:
        def validate(self, *_args, **_kwargs):
            raise RuntimeError("boom")

    _patch_runtime_dependencies(monkeypatch, validator_factory=lambda: ExplodingValidator())
    monkeypatch.setattr(cli_app.console, "print", lambda *_args, **_kwargs: None)

    DummyRuntime.next_exception = None
    cli_app.run(
        workflow,
        sandbox=False,
        storage="memory",
        param=None,
        verbose=True,
        mock_all=False,
        real_all=False,
        mock=None,
        real=None,
        log_level=None,
        log_format="rich",
    )


def test_run_failure_without_error_message(tmp_path, monkeypatch):
    workflow = tmp_path / "workflow.tac"
    workflow.write_text("print('hi')")

    _patch_runtime_dependencies(monkeypatch)
    monkeypatch.setattr(cli_app.console, "print", lambda *_args, **_kwargs: None)

    DummyRuntime.next_result = {"success": False}
    DummyRuntime.next_exception = None

    with pytest.raises(typer.Exit):
        cli_app.run(
            workflow,
            sandbox=False,
            storage="memory",
            param=None,
            mock_all=False,
            real_all=False,
            mock=None,
            real=None,
            log_level=None,
            log_format="rich",
        )


def test_run_execution_error(tmp_path, monkeypatch):
    workflow = tmp_path / "workflow.tac"
    workflow.write_text("print('hi')")

    _patch_runtime_dependencies(monkeypatch)
    monkeypatch.setattr(cli_app.console, "print", lambda *_args, **_kwargs: None)

    DummyRuntime.next_result = None
    DummyRuntime.next_exception = RuntimeError("boom")

    with pytest.raises(typer.Exit):
        cli_app.run(
            workflow,
            sandbox=False,
            storage="memory",
            param=None,
            mock_all=False,
            real_all=False,
            mock=None,
            real=None,
            log_level=None,
            log_format="rich",
        )


def test_run_inserts_cli_channel_when_missing(tmp_path, monkeypatch):
    workflow = tmp_path / "workflow.tac"
    workflow.write_text("print('hi')")

    _patch_runtime_dependencies(monkeypatch)
    monkeypatch.setattr(cli_app.console, "print", lambda *_args, **_kwargs: None)

    DummyRuntime.next_exception = None
    cli_app.run(
        workflow,
        sandbox=False,
        storage="memory",
        param=None,
        mock_all=False,
        real_all=False,
        mock=None,
        real=None,
        log_level=None,
        log_format="rich",
    )

    channels = DummyControlLoopHandler.last_channels
    assert channels
    assert any(isinstance(channel, DummyCLIControlChannel) for channel in channels)


def test_run_respects_existing_cli_channel(tmp_path, monkeypatch):
    workflow = tmp_path / "workflow.tac"
    workflow.write_text("print('hi')")

    _patch_runtime_dependencies(monkeypatch)
    monkeypatch.setattr(
        "tactus.adapters.channels.load_default_channels",
        lambda **_kwargs: [DummyCLIControlChannel()],
    )
    monkeypatch.setattr(cli_app.console, "print", lambda *_args, **_kwargs: None)

    DummyRuntime.next_exception = None
    cli_app.run(
        workflow,
        sandbox=False,
        storage="memory",
        param=None,
        mock_all=False,
        real_all=False,
        mock=None,
        real=None,
        log_level=None,
        log_format="rich",
    )

    channels = DummyControlLoopHandler.last_channels
    assert channels and len(channels) == 1


def test_run_mocking_flags_register_tools(tmp_path, monkeypatch):
    workflow = tmp_path / "workflow.tac"
    workflow.write_text("print('hi')")

    class DummyMockManager:
        def __init__(self):
            self.enabled = []
            self.disabled = []
            self.registered = []

        def enable_mock(self, name=None):
            self.enabled.append(name or "__all__")

        def disable_mock(self, name=None):
            self.disabled.append(name or "__all__")

        def register_mock(self, name, _config):
            self.registered.append(name)

    class DummyMockConfig:
        def __init__(self, **_kwargs):
            pass

    _patch_runtime_dependencies(monkeypatch)
    monkeypatch.setattr("tactus.core.mocking.MockManager", DummyMockManager)
    monkeypatch.setattr("tactus.core.mocking.MockConfig", DummyMockConfig)
    monkeypatch.setattr(cli_app.console, "print", lambda *_args, **_kwargs: None)

    DummyRuntime.next_exception = None
    cli_app.run(
        workflow,
        sandbox=False,
        storage="memory",
        param=None,
        mock_all=True,
        real_all=False,
        mock=["tool_a"],
        real=["tool_b"],
        log_level=None,
        log_format="rich",
    )


def test_run_real_all_disables_mocking(tmp_path, monkeypatch):
    workflow = tmp_path / "workflow.tac"
    workflow.write_text("print('hi')")

    class DummyMockManager:
        def __init__(self):
            self.enabled = []
            self.disabled = []

        def enable_mock(self, name=None):
            self.enabled.append(name or "__all__")

        def disable_mock(self, name=None):
            self.disabled.append(name or "__all__")

        def register_mock(self, name, _config):
            self.enabled.append(name)

    class DummyMockConfig:
        def __init__(self, **_kwargs):
            pass

    _patch_runtime_dependencies(monkeypatch)
    monkeypatch.setattr("tactus.core.mocking.MockManager", DummyMockManager)
    monkeypatch.setattr("tactus.core.mocking.MockConfig", DummyMockConfig)
    monkeypatch.setattr(cli_app.console, "print", lambda *_args, **_kwargs: None)

    DummyRuntime.next_exception = None
    cli_app.run(
        workflow,
        sandbox=False,
        storage="memory",
        param=None,
        mock_all=False,
        real_all=True,
        mock=None,
        real=None,
        log_level=None,
        log_format="rich",
    )


def test_run_sandbox_success(tmp_path, monkeypatch):
    workflow = tmp_path / "workflow.tac"
    workflow.write_text("print('hi')")

    class DummyRunner:
        def __init__(self, _config):
            pass

        async def run(self, **_kwargs):
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                result="ok",
                metadata={"state": {"x": 1}, "iterations": 2, "tools_used": ["done"]},
            )

    class RequiredSandboxConfig(DummySandboxConfig):
        def __init__(self, **kwargs):
            super().__init__(should_use=True, explicit_disabled=False, error_if_unavailable=False)
            self.env = {}

    _patch_runtime_dependencies(
        monkeypatch, sandbox_config=RequiredSandboxConfig, docker_available=True
    )
    monkeypatch.setattr("tactus.sandbox.ContainerRunner", DummyRunner)
    monkeypatch.setattr(cli_app.console, "print", lambda *_args, **_kwargs: None)

    cli_app.run(
        workflow,
        sandbox=True,
        storage="memory",
        param=None,
        openai_api_key=None,
        mock_all=False,
        real_all=False,
        mock=None,
        real=None,
        log_level=None,
        log_format="rich",
    )


def test_run_sandbox_failure_verbose(tmp_path, monkeypatch):
    workflow = tmp_path / "workflow.tac"
    workflow.write_text("print('hi')")

    class DummyRunner:
        def __init__(self, _config):
            pass

        async def run(self, **_kwargs):
            return ExecutionResult(
                status=ExecutionStatus.ERROR,
                error="boom",
                traceback="traceback here",
            )

    class RequiredSandboxConfig(DummySandboxConfig):
        def __init__(self, **kwargs):
            super().__init__(should_use=True, explicit_disabled=False, error_if_unavailable=False)
            self.env = {}

    _patch_runtime_dependencies(
        monkeypatch, sandbox_config=RequiredSandboxConfig, docker_available=True
    )
    monkeypatch.setattr("tactus.sandbox.ContainerRunner", DummyRunner)
    monkeypatch.setattr(cli_app.console, "print", lambda *_args, **_kwargs: None)

    with pytest.raises(typer.Exit):
        cli_app.run(
            workflow,
            sandbox=True,
            storage="memory",
            param=None,
            verbose=True,
            openai_api_key=None,
            mock_all=False,
            real_all=False,
            mock=None,
            real=None,
            log_level=None,
            log_format="rich",
        )


def test_run_sandbox_failure_not_verbose(tmp_path, monkeypatch):
    workflow = tmp_path / "workflow.tac"
    workflow.write_text("print('hi')")

    class DummyRunner:
        def __init__(self, _config):
            pass

        async def run(self, **_kwargs):
            return ExecutionResult(
                status=ExecutionStatus.ERROR,
                error="boom",
                traceback="traceback here",
            )

    class RequiredSandboxConfig(DummySandboxConfig):
        def __init__(self, **kwargs):
            super().__init__(should_use=True, explicit_disabled=False, error_if_unavailable=False)
            self.env = {}

    _patch_runtime_dependencies(
        monkeypatch, sandbox_config=RequiredSandboxConfig, docker_available=True
    )
    monkeypatch.setattr("tactus.sandbox.ContainerRunner", DummyRunner)
    monkeypatch.setattr(cli_app.console, "print", lambda *_args, **_kwargs: None)

    with pytest.raises(typer.Exit):
        cli_app.run(
            workflow,
            sandbox=True,
            storage="memory",
            param=None,
            verbose=False,
            openai_api_key=None,
            mock_all=False,
            real_all=False,
            mock=None,
            real=None,
            log_level=None,
            log_format="rich",
        )


def test_run_sets_api_key_for_sandbox(tmp_path, monkeypatch):
    workflow = tmp_path / "workflow.tac"
    workflow.write_text("print('hi')")

    class DummyRunner:
        def __init__(self, _config):
            pass

        async def run(self, **_kwargs):
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                result="ok",
                metadata={},
            )

    class RequiredSandboxConfig(DummySandboxConfig):
        def __init__(self, **kwargs):
            super().__init__(should_use=True, explicit_disabled=False, error_if_unavailable=False)
            self.env = {}

    _patch_runtime_dependencies(
        monkeypatch, sandbox_config=RequiredSandboxConfig, docker_available=True
    )
    monkeypatch.setattr("tactus.sandbox.ContainerRunner", DummyRunner)
    monkeypatch.setattr(cli_app.console, "print", lambda *_args, **_kwargs: None)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    cli_app.run(
        workflow,
        sandbox=True,
        storage="memory",
        param=None,
        openai_api_key="test-key",
        mock_all=False,
        real_all=False,
        mock=None,
        real=None,
        log_level=None,
        log_format="rich",
    )

    assert os.environ.get("OPENAI_API_KEY") == "test-key"


def test_run_success_displays_state_and_tools(tmp_path, monkeypatch):
    workflow = tmp_path / "workflow.tac"
    workflow.write_text("print('hi')")

    _patch_runtime_dependencies(monkeypatch)
    monkeypatch.setattr(cli_app.console, "print", lambda *_args, **_kwargs: None)

    from tactus.protocols.result import TactusResult

    DummyRuntime.next_result = {
        "success": True,
        "result": TactusResult(output={"ok": True}),
        "state": {"k": "v"},
        "iterations": 3,
        "tools_used": ["done"],
    }
    DummyRuntime.next_exception = None

    cli_app.run(
        workflow,
        sandbox=False,
        storage="memory",
        param=None,
        mock_all=False,
        real_all=False,
        mock=None,
        real=None,
        log_level=None,
        log_format="rich",
    )


def test_run_failure_raises_exit(tmp_path, monkeypatch):
    workflow = tmp_path / "workflow.tac"
    workflow.write_text("print('hi')")

    _patch_runtime_dependencies(monkeypatch)
    monkeypatch.setattr(cli_app.console, "print", lambda *_args, **_kwargs: None)

    DummyRuntime.next_result = {"success": False, "error": "boom"}
    DummyRuntime.next_exception = None

    with pytest.raises(typer.Exit):
        cli_app.run(
            workflow,
            sandbox=False,
            storage="memory",
            param=None,
            mock_all=False,
            real_all=False,
            mock=None,
            real=None,
            log_level=None,
            log_format="rich",
        )


def test_run_waiting_for_human_cause(tmp_path, monkeypatch):
    from tactus.core.exceptions import ProcedureWaitingForHuman

    workflow = tmp_path / "workflow.tac"
    workflow.write_text("print('hi')")

    _patch_runtime_dependencies(monkeypatch)
    monkeypatch.setattr(cli_app.console, "print", lambda *_args, **_kwargs: None)

    cause = ProcedureWaitingForHuman("pause", pending_message_id="msg-2")
    exc = RuntimeError("wrapped")
    exc.__cause__ = cause
    DummyRuntime.next_result = None
    DummyRuntime.next_exception = exc

    cli_app.run(
        workflow,
        sandbox=False,
        storage="memory",
        param=None,
        mock_all=False,
        real_all=False,
        mock=None,
        real=None,
        log_level=None,
        log_format="rich",
    )
