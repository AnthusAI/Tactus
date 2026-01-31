import asyncio
import logging
import sys
import textwrap
from pathlib import Path

import pytest

from tactus.broker.stdio import STDIO_TRANSPORT_VALUE
from tactus.sandbox.config import SandboxConfig
from tactus.sandbox import container_runner as container_runner_module
from tactus.sandbox.container_runner import ContainerRunner
from tactus.sandbox.protocol import ExecutionRequest, ExecutionResult, ExecutionStatus


def test_build_docker_command_defaults_network_none(tmp_path: Path) -> None:
    runner = ContainerRunner(SandboxConfig())

    cmd = runner._build_docker_command(
        working_dir=tmp_path,
        mcp_servers_path=None,
        extra_env={"TACTUS_BROKER_SOCKET": STDIO_TRANSPORT_VALUE},
        execution_id="abc123",
    )

    network_idx = cmd.index("--network")
    assert cmd[network_idx + 1] == "bridge"


def test_build_docker_command_allows_network_override(tmp_path: Path) -> None:
    runner = ContainerRunner(SandboxConfig(network="bridge"))

    cmd = runner._build_docker_command(
        working_dir=tmp_path,
        mcp_servers_path=None,
        extra_env={"TACTUS_BROKER_SOCKET": STDIO_TRANSPORT_VALUE},
        execution_id="abc123",
    )

    network_idx = cmd.index("--network")
    assert cmd[network_idx + 1] == "bridge"


def test_build_docker_command_filters_secret_env_vars(tmp_path: Path) -> None:
    runner = ContainerRunner(
        SandboxConfig(
            env={
                "OPENAI_API_KEY": "sk-test-should-not-leak",
                "SAFE_SETTING": "ok",
            }
        )
    )

    cmd = runner._build_docker_command(
        working_dir=tmp_path,
        mcp_servers_path=None,
        extra_env={"TACTUS_BROKER_SOCKET": STDIO_TRANSPORT_VALUE},
        execution_id="abc123",
    )

    assert "SAFE_SETTING=ok" in cmd
    assert "OPENAI_API_KEY=sk-test-should-not-leak" not in cmd


@pytest.mark.asyncio
async def test_run_copies_source_directory_contents(tmp_path: Path, monkeypatch) -> None:
    source_dir = tmp_path / "src"
    source_dir.mkdir()
    source_file = source_dir / "main.tac"
    source_file.write_text("return {}")
    (source_dir / "notes.txt").write_text("hello")
    subdir = source_dir / "data"
    subdir.mkdir()
    (subdir / "values.txt").write_text("ok")

    config = SandboxConfig(mount_current_dir=False)
    runner = ContainerRunner(config)
    observed = {}

    def fake_build_docker_command(*_args, **kwargs):
        working_dir = kwargs["working_dir"]
        observed["working_dir"] = working_dir
        assert (working_dir / "notes.txt").exists()
        assert (working_dir / "data" / "values.txt").exists()
        return ["docker"]

    async def fake_run_container(*_args, **_kwargs):
        return ExecutionResult.success(result="ok")

    monkeypatch.setattr(runner, "_ensure_sandbox_up_to_date", lambda **_kwargs: None)
    monkeypatch.setattr(runner, "_build_docker_command", fake_build_docker_command)
    monkeypatch.setattr(runner, "_run_container", fake_run_container)

    result = await runner.run(source="return {}", source_file_path=str(source_file))

    assert result.status == ExecutionStatus.SUCCESS
    assert observed["working_dir"] is not None
    assert not observed["working_dir"].exists()


@pytest.mark.asyncio
async def test_run_container_closes_stdin_after_result() -> None:
    runner = ContainerRunner(SandboxConfig())

    request = ExecutionRequest(
        source="Procedure { function() return { ok = true } end }",
        params={},
        execution_id="abc123",
        source_file_path=None,
        format="lua",
    )

    script = textwrap.dedent(
        """
        import sys
        from tactus.sandbox.protocol import ExecutionResult, RESULT_START_MARKER, RESULT_END_MARKER

        sys.stdin.readline()

        result = ExecutionResult.success(result={"ok": True})
        sys.stdout.write(f"{RESULT_START_MARKER}\\n{result.to_json()}\\n{RESULT_END_MARKER}\\n")
        sys.stdout.flush()

        # Keep the process alive until stdin is closed to simulate Docker attach behavior.
        while sys.stdin.readline():
            pass
        """
    ).strip()

    result = await runner._run_container(
        docker_cmd=[sys.executable, "-c", script],
        request=request,
        timeout=10,
    )

    assert result.status.value == "success"
    assert result.result == {"ok": True}


def test_default_volume_current_dir_included(tmp_path: Path) -> None:
    """Verify current directory mount is included by default."""
    runner = ContainerRunner(SandboxConfig(mount_current_dir=True))

    cmd = runner._build_docker_command(
        working_dir=tmp_path,
        mcp_servers_path=None,
        extra_env={"TACTUS_BROKER_SOCKET": STDIO_TRANSPORT_VALUE},
        execution_id="abc123",
    )

    # Find all -v flags and check that current dir is mounted
    volume_mounts = []
    for i, arg in enumerate(cmd):
        if arg == "-v":
            volume_mounts.append(cmd[i + 1])

    # Should have at least the working_dir mount and the default current dir mount
    assert any(":/workspace" in v for v in volume_mounts)
    # Check that the volumes config field has the default mount
    assert ".:/workspace:rw" in runner.config.volumes


def test_disable_default_current_dir_mount(tmp_path: Path) -> None:
    """Verify current directory mount can be disabled."""
    runner = ContainerRunner(SandboxConfig(mount_current_dir=False))

    # Check that the volumes config field does NOT have the default mount
    assert ".:/workspace:rw" not in runner.config.volumes


def test_user_volumes_supplement_defaults(tmp_path: Path) -> None:
    """Verify user volumes work with default mount."""
    runner = ContainerRunner(SandboxConfig(mount_current_dir=True, volumes=["./custom:/custom:ro"]))

    cmd = runner._build_docker_command(
        working_dir=tmp_path,
        mcp_servers_path=None,
        extra_env={"TACTUS_BROKER_SOCKET": STDIO_TRANSPORT_VALUE},
        execution_id="abc123",
        volume_base_dir=tmp_path,
    )

    # Find all -v flags
    volume_mounts = []
    for i, arg in enumerate(cmd):
        if arg == "-v":
            volume_mounts.append(cmd[i + 1])

    # Should have both default and custom volumes
    assert ".:/workspace:rw" in runner.config.volumes
    assert "./custom:/custom:ro" in runner.config.volumes
    # The custom mount should be in the docker command (after normalization)
    assert any("/custom" in v for v in volume_mounts)


def test_config_volumes_added_to_list() -> None:
    """Verify that the default volume is added during config initialization."""
    # Default behavior - should add current dir mount
    config = SandboxConfig()
    assert ".:/workspace:rw" in config.volumes

    # Disabled - should not add current dir mount
    config_disabled = SandboxConfig(mount_current_dir=False)
    assert ".:/workspace:rw" not in config_disabled.volumes

    # With custom volumes - should have both
    config_custom = SandboxConfig(volumes=["./data:/data:ro"])
    assert ".:/workspace:rw" in config_custom.volumes
    assert "./data:/data:ro" in config_custom.volumes


def test_normalize_volume_spec_relative_and_named(tmp_path: Path) -> None:
    runner = ContainerRunner(SandboxConfig())
    normalized = runner._normalize_volume_spec("./data:/data:ro", base_dir=tmp_path)
    assert normalized.startswith(str(tmp_path))
    assert normalized.endswith(":/data:ro")

    unchanged = runner._normalize_volume_spec("named_volume:/data:ro", base_dir=tmp_path)
    assert unchanged == "named_volume:/data:ro"


def test_find_tactus_source_dir_env_and_cwd(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    (repo / "tactus").mkdir(parents=True)
    (repo / "pyproject.toml").write_text("x")

    monkeypatch.setattr(container_runner_module.os, "environ", {"TACTUS_DEV_PATH": str(Path.cwd())})
    runner = ContainerRunner(SandboxConfig(dev_mode=True))
    assert runner._find_tactus_source_dir() == Path.cwd()

    fake_module_root = tmp_path / "module_root"
    (fake_module_root / "tactus").mkdir(parents=True)
    import tactus

    monkeypatch.setattr(tactus, "__file__", str(fake_module_root / "tactus" / "__init__.py"))
    monkeypatch.setattr(container_runner_module.os, "environ", {})
    monkeypatch.chdir(repo)
    assert runner._find_tactus_source_dir() == repo


def test_build_docker_command_dev_mode_mount(tmp_path: Path, monkeypatch) -> None:
    runner = ContainerRunner(SandboxConfig(dev_mode=True))
    monkeypatch.setattr(runner, "_find_tactus_source_dir", lambda: tmp_path)

    cmd = runner._build_docker_command(
        working_dir=tmp_path,
        mcp_servers_path=None,
        extra_env={"TACTUS_BROKER_SOCKET": STDIO_TRANSPORT_VALUE},
        execution_id="abc123",
    )

    assert f"{tmp_path}/tactus:/app/tactus:ro" in cmd


def test_ensure_sandbox_up_to_date_skips_for_ide(monkeypatch) -> None:
    runner = ContainerRunner(SandboxConfig())
    called = {}

    def fail_if_called(*args, **kwargs):
        called["hit"] = True

    monkeypatch.setattr(runner.docker_manager, "needs_rebuild", fail_if_called)
    runner._ensure_sandbox_up_to_date(skip_for_ide=True)
    assert called == {}


def test_ensure_sandbox_up_to_date_disabled_env(monkeypatch) -> None:
    runner = ContainerRunner(SandboxConfig())
    monkeypatch.setenv("TACTUS_AUTO_REBUILD_SANDBOX", "false")

    called = {}

    def fail_if_called(*args, **kwargs):
        called["hit"] = True

    monkeypatch.setattr(runner.docker_manager, "needs_rebuild", fail_if_called)
    runner._ensure_sandbox_up_to_date()
    assert called == {}


@pytest.mark.asyncio
async def test_run_tcp_requires_network(monkeypatch, tmp_path: Path) -> None:
    runner = ContainerRunner(SandboxConfig(broker_transport="tcp", network="none"))

    monkeypatch.setattr(runner, "_ensure_sandbox_up_to_date", lambda **_kwargs: None)

    result = await runner.run(source="Procedure { function() end }")

    assert result.status.value == "error"
    assert result.error_type == "SandboxError"
    assert "requires container networking" in result.error


@pytest.mark.asyncio
async def test_run_tls_requires_cert_files(monkeypatch, tmp_path: Path) -> None:
    runner = ContainerRunner(SandboxConfig(broker_transport="tls", network="bridge"))

    monkeypatch.setattr(runner, "_ensure_sandbox_up_to_date", lambda **_kwargs: None)

    result = await runner.run(source="Procedure { function() end }")

    assert result.status.value == "error"
    assert result.error_type == "SandboxError"
    assert "requires sandbox.broker_tls_cert_file" in result.error


@pytest.mark.asyncio
async def test_run_tcp_missing_bound_port(monkeypatch) -> None:
    runner = ContainerRunner(SandboxConfig(broker_transport="tcp", network="bridge"))

    class FakeServer:
        def __init__(self, *args, **kwargs):
            self.bound_port = None

        async def start(self):
            return None

        async def serve(self):
            return None

        async def aclose(self):
            return None

    monkeypatch.setattr("tactus.broker.server.TcpBrokerServer", FakeServer)
    monkeypatch.setattr("tactus.broker.server.OpenAIChatBackend", lambda api_key=None: object())
    monkeypatch.setattr(runner, "_ensure_sandbox_up_to_date", lambda **_kwargs: None)
    monkeypatch.setattr(runner, "_build_docker_command", lambda **_kwargs: ["docker"])

    result = await runner.run(source="Procedure { function() end }")

    assert result.status.value == "error"
    assert result.error_type == "SandboxError"
    assert "Failed to determine TCP broker listen port" in result.error


@pytest.mark.asyncio
async def test_run_tcp_broker_serve_error_is_ignored(monkeypatch) -> None:
    runner = ContainerRunner(SandboxConfig(broker_transport="tcp", network="bridge"))

    class FakeServer:
        def __init__(self, *args, **kwargs):
            self.bound_port = 1234
            self.closed = False

        async def start(self):
            return None

        async def serve(self):
            raise RuntimeError("boom")

        async def aclose(self):
            self.closed = True

    fake_server = FakeServer()

    monkeypatch.setattr("tactus.broker.server.TcpBrokerServer", lambda *args, **kwargs: fake_server)
    monkeypatch.setattr("tactus.broker.server.OpenAIChatBackend", lambda api_key=None: object())
    monkeypatch.setattr(runner, "_ensure_sandbox_up_to_date", lambda **_kwargs: None)
    monkeypatch.setattr(runner, "_build_docker_command", lambda **_kwargs: ["docker"])

    async def fake_run_container(*_args, **_kwargs):
        await asyncio.sleep(0)
        return ExecutionResult.success(result={"ok": True})

    monkeypatch.setattr(runner, "_run_container", fake_run_container)

    result = await runner.run(source="Procedure { function() end }")

    assert result.status.value == "success"
    assert fake_server.closed is True


@pytest.mark.asyncio
async def test_run_tcp_passes_openai_key(monkeypatch) -> None:
    runner = ContainerRunner(SandboxConfig(broker_transport="tcp", network="bridge"))

    captured = {}

    class FakeServer:
        def __init__(self, *args, **kwargs):
            self.bound_port = 4321

        async def start(self):
            return None

        async def serve(self):
            return None

        async def aclose(self):
            return None

    def fake_openai_backend(api_key=None):
        captured["api_key"] = api_key
        return object()

    async def fake_run_container(*_args, **_kwargs):
        return ExecutionResult.success(result={"ok": True})

    monkeypatch.setattr("tactus.broker.server.TcpBrokerServer", FakeServer)
    monkeypatch.setattr("tactus.broker.server.OpenAIChatBackend", fake_openai_backend)
    monkeypatch.setattr(runner, "_ensure_sandbox_up_to_date", lambda **_kwargs: None)
    monkeypatch.setattr(runner, "_build_docker_command", lambda **_kwargs: ["docker"])
    monkeypatch.setattr(runner, "_run_container", fake_run_container)

    result = await runner.run(
        source="Procedure { function() end }",
        llm_backend_config={"openai_api_key": "sk-openai"},
    )

    assert result.status.value == "success"
    assert captured["api_key"] == "sk-openai"


@pytest.mark.asyncio
async def test_run_stdio_sets_broker_env(monkeypatch) -> None:
    runner = ContainerRunner(SandboxConfig(broker_transport="stdio", network="bridge"))

    monkeypatch.setattr(runner, "_ensure_sandbox_up_to_date", lambda **_kwargs: None)

    captured = {}

    def fake_build_docker_command(*_args, **kwargs):
        captured["extra_env"] = kwargs.get("extra_env")
        return ["docker"]

    async def fake_run_container(*_args, **_kwargs):
        return ExecutionResult.success(result={"ok": True})

    monkeypatch.setattr(runner, "_build_docker_command", fake_build_docker_command)
    monkeypatch.setattr(runner, "_run_container", fake_run_container)

    result = await runner.run(source="Procedure { function() end }")

    assert result.status.value == "success"
    assert "TACTUS_BROKER_SOCKET" in captured["extra_env"]


@pytest.mark.asyncio
async def test_run_copies_source_dir_into_temp_workspace(monkeypatch, tmp_path: Path) -> None:
    runner = ContainerRunner(SandboxConfig(mount_current_dir=False))

    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "procedure.tac").write_text("main = Procedure { function() end }")
    (src_dir / "data.txt").write_text("data")
    (src_dir / ".hidden").mkdir()
    (src_dir / ".hidden" / "secret.txt").write_text("secret")
    (src_dir / "subdir").mkdir()
    (src_dir / "subdir" / "nested.txt").write_text("nested")

    temp_dir = tmp_path / "workspace"
    temp_dir.mkdir()

    async def fake_run_container(_cmd, _request, **_kwargs):
        assert (temp_dir / "procedure.tac").exists()
        assert (temp_dir / "data.txt").exists()
        assert (temp_dir / "subdir" / "nested.txt").exists()
        assert not (temp_dir / ".hidden").exists()
        return ExecutionResult.success(result={"ok": True})

    monkeypatch.setattr(runner, "_ensure_sandbox_up_to_date", lambda **_kwargs: None)
    monkeypatch.setattr(container_runner_module.tempfile, "mkdtemp", lambda prefix: str(temp_dir))
    monkeypatch.setattr(runner, "_build_docker_command", lambda **_kwargs: ["docker"])
    monkeypatch.setattr(runner, "_run_container", fake_run_container)

    result = await runner.run(
        source="main = Procedure { function() end }",
        source_file_path=str(src_dir / "procedure.tac"),
    )

    assert result.status.value == "success"


@pytest.mark.asyncio
async def test_run_handles_volume_base_dir_resolve_error(monkeypatch, tmp_path: Path) -> None:
    runner = ContainerRunner(SandboxConfig(mount_current_dir=False))

    source_file = tmp_path / "proc" / "procedure.tac"
    source_file.parent.mkdir()
    source_file.write_text("main = Procedure { function() end }")

    monkeypatch.setattr(runner, "_ensure_sandbox_up_to_date", lambda **_kwargs: None)

    captured = {}

    def fake_build_docker_command(*_args, **kwargs):
        captured["volume_base_dir"] = kwargs.get("volume_base_dir")
        return ["docker"]

    async def fake_run_container(*_args, **_kwargs):
        return ExecutionResult.success(result={"ok": True})

    original_resolve = container_runner_module.Path.resolve

    def fake_resolve(self, *args, **kwargs):
        if self == source_file:
            raise RuntimeError("boom")
        return original_resolve(self, *args, **kwargs)

    monkeypatch.setattr(container_runner_module.Path, "resolve", fake_resolve)
    monkeypatch.setattr(runner, "_build_docker_command", fake_build_docker_command)
    monkeypatch.setattr(runner, "_run_container", fake_run_container)

    result = await runner.run(
        source="main = Procedure { function() end }",
        source_file_path=str(source_file),
    )

    assert result.status.value == "success"
    assert captured["volume_base_dir"] is None


@pytest.mark.asyncio
async def test_run_skips_copy_when_source_dir_missing(monkeypatch, tmp_path: Path) -> None:
    runner = ContainerRunner(SandboxConfig(mount_current_dir=False))

    missing_file = tmp_path / "missing" / "procedure.tac"
    temp_dir = tmp_path / "workspace"
    temp_dir.mkdir()

    async def fake_run_container(_cmd, _request, **_kwargs):
        assert not list(temp_dir.iterdir())
        return ExecutionResult.success(result={"ok": True})

    monkeypatch.setattr(runner, "_ensure_sandbox_up_to_date", lambda **_kwargs: None)
    monkeypatch.setattr(container_runner_module.tempfile, "mkdtemp", lambda prefix: str(temp_dir))
    monkeypatch.setattr(runner, "_build_docker_command", lambda **_kwargs: ["docker"])
    monkeypatch.setattr(runner, "_run_container", fake_run_container)

    result = await runner.run(
        source="main = Procedure { function() end }",
        source_file_path=str(missing_file),
    )

    assert result.status.value == "success"


def test_ensure_sandbox_up_to_date_rebuild_success(monkeypatch, tmp_path: Path) -> None:
    runner = ContainerRunner(SandboxConfig())
    monkeypatch.setenv("TACTUS_AUTO_REBUILD_SANDBOX", "true")

    monkeypatch.setattr(
        "tactus.sandbox.container_runner.resolve_dockerfile_path",
        lambda root: (tmp_path / "Dockerfile", "source"),
    )
    monkeypatch.setattr(
        "tactus.sandbox.container_runner.calculate_source_hash", lambda root: "hash"
    )
    monkeypatch.setattr("tactus.sandbox.container_runner.Path", Path)
    monkeypatch.setattr(
        "tactus.sandbox.container_runner.__file__",
        str(tmp_path / "tactus" / "sandbox" / "container_runner.py"),
    )
    monkeypatch.setattr(runner.docker_manager, "needs_rebuild", lambda version, current_hash: True)
    monkeypatch.setattr(runner.docker_manager, "build_image", lambda **kwargs: (True, "ok"))

    runner._ensure_sandbox_up_to_date()


def test_ensure_sandbox_up_to_date_rebuild_failure(monkeypatch, tmp_path: Path) -> None:
    runner = ContainerRunner(SandboxConfig())
    monkeypatch.setenv("TACTUS_AUTO_REBUILD_SANDBOX", "true")

    monkeypatch.setattr(
        "tactus.sandbox.container_runner.resolve_dockerfile_path",
        lambda root: (tmp_path / "Dockerfile", "source"),
    )
    monkeypatch.setattr(
        "tactus.sandbox.container_runner.calculate_source_hash", lambda root: "hash"
    )
    monkeypatch.setattr("tactus.sandbox.container_runner.Path", Path)
    monkeypatch.setattr(
        "tactus.sandbox.container_runner.__file__",
        str(tmp_path / "tactus" / "sandbox" / "container_runner.py"),
    )
    monkeypatch.setattr(runner.docker_manager, "needs_rebuild", lambda version, current_hash: True)
    monkeypatch.setattr(runner.docker_manager, "build_image", lambda **kwargs: (False, "nope"))

    with pytest.raises(RuntimeError):
        runner._ensure_sandbox_up_to_date()


@pytest.mark.asyncio
async def test_run_rejects_tcp_without_network(tmp_path: Path, monkeypatch) -> None:
    runner = ContainerRunner(SandboxConfig(network="none", broker_transport="tcp"))
    monkeypatch.setattr(runner, "_ensure_sandbox_up_to_date", lambda *args, **kwargs: None)

    result = await runner.run(source="main", working_dir=tmp_path)
    assert result.status.value == "error"
    assert "broker_transport requires container networking" in (result.error or "")


@pytest.mark.asyncio
async def test_run_rejects_unknown_broker_transport(tmp_path: Path, monkeypatch) -> None:
    runner = ContainerRunner(SandboxConfig(broker_transport="weird"))
    monkeypatch.setattr(runner, "_ensure_sandbox_up_to_date", lambda *args, **kwargs: None)

    result = await runner.run(source="main", working_dir=tmp_path)
    assert result.status.value == "error"
    assert "Unsupported sandbox.broker_transport" in (result.error or "")


@pytest.mark.asyncio
async def test_run_returns_execution_result(tmp_path: Path, monkeypatch) -> None:
    runner = ContainerRunner(SandboxConfig())
    monkeypatch.setattr(runner, "_ensure_sandbox_up_to_date", lambda *args, **kwargs: None)

    async def fake_run_container(*args, **kwargs):
        return ExecutionResult.success(result={"ok": True})

    monkeypatch.setattr(runner, "_run_container", fake_run_container)
    result = await runner.run(source="main", working_dir=tmp_path)

    assert result.status.value == "success"
    assert result.result == {"ok": True}
    assert result.duration_seconds >= 0


@pytest.mark.asyncio
async def test_run_returns_timeout_result(monkeypatch):
    runner = ContainerRunner(SandboxConfig())

    async def raise_timeout(*_args, **_kwargs):
        raise asyncio.TimeoutError

    monkeypatch.setattr(runner, "_ensure_sandbox_up_to_date", lambda **_kwargs: None)
    monkeypatch.setattr(runner, "_run_container", raise_timeout)

    result = await runner.run(source="main = Procedure { function() end }")

    assert result.status.value == "timeout"


@pytest.mark.asyncio
async def test_run_returns_failure_on_exception(monkeypatch):
    runner = ContainerRunner(SandboxConfig())

    async def raise_error(*_args, **_kwargs):
        raise ValueError("boom")

    monkeypatch.setattr(runner, "_ensure_sandbox_up_to_date", lambda **_kwargs: None)
    monkeypatch.setattr(runner, "_run_container", raise_error)

    result = await runner.run(source="main = Procedure { function() end }")

    assert result.status.value == "error"
    assert result.error_type == "ValueError"


@pytest.mark.asyncio
async def test_run_tcp_broker_missing_bound_port(monkeypatch):
    runner = ContainerRunner(SandboxConfig(broker_transport="tcp", network="bridge"))

    class FakeServer:
        bound_port = None

        def __init__(self, *args, **kwargs):
            pass

        async def start(self):
            return None

        async def aclose(self):
            return None

    monkeypatch.setattr(runner, "_ensure_sandbox_up_to_date", lambda **_kwargs: None)
    monkeypatch.setattr("tactus.broker.server.TcpBrokerServer", FakeServer)
    monkeypatch.setattr("tactus.broker.server.OpenAIChatBackend", lambda api_key=None: object())

    result = await runner.run(source="main = Procedure { function() end }")

    assert result.status.value == "error"
    assert result.error_type == "SandboxError"
    assert "Failed to determine TCP broker listen port" in result.error


@pytest.mark.asyncio
async def test_run_tcp_broker_executes_and_closes(monkeypatch):
    runner = ContainerRunner(SandboxConfig(broker_transport="tcp", network="bridge"))
    calls = {"close": 0, "serve": 0}

    class FakeServer:
        bound_port = 5555

        def __init__(self, *args, **kwargs):
            pass

        async def start(self):
            return None

        async def serve(self):
            calls["serve"] += 1
            raise RuntimeError("serve failed")

        async def aclose(self):
            calls["close"] += 1

    async def fake_run_container(*_args, **_kwargs):
        return ExecutionResult.success(result={"ok": True})

    monkeypatch.setattr(runner, "_ensure_sandbox_up_to_date", lambda **_kwargs: None)
    monkeypatch.setattr("tactus.broker.server.TcpBrokerServer", FakeServer)
    monkeypatch.setattr("tactus.broker.server.OpenAIChatBackend", lambda api_key=None: object())
    monkeypatch.setattr(runner, "_run_container", fake_run_container)

    result = await runner.run(source="main = Procedure { function() end }")

    assert result.status.value == "success"
    assert calls["close"] == 1


@pytest.mark.asyncio
async def test_run_tls_with_certificates(monkeypatch, tmp_path: Path):
    cert_path = tmp_path / "cert.pem"
    key_path = tmp_path / "key.pem"
    cert_path.write_text("cert")
    key_path.write_text("key")

    runner = ContainerRunner(
        SandboxConfig(
            broker_transport="tls",
            network="bridge",
            broker_tls_cert_file=str(cert_path),
            broker_tls_key_file=str(key_path),
        )
    )

    class FakeServer:
        bound_port = 5555

        def __init__(self, *args, **kwargs):
            pass

        async def start(self):
            return None

        async def serve(self):
            await asyncio.sleep(0)

        async def aclose(self):
            raise RuntimeError("close failed")

    async def fake_run_container(*_args, **_kwargs):
        return ExecutionResult.success(result={"ok": True})

    class FakeSSLContext:
        def __init__(self, *_args, **_kwargs):
            self.loaded = False

        def load_cert_chain(self, certfile=None, keyfile=None):
            self.loaded = True

    monkeypatch.setattr(runner, "_ensure_sandbox_up_to_date", lambda **_kwargs: None)
    monkeypatch.setattr("tactus.broker.server.TcpBrokerServer", FakeServer)
    monkeypatch.setattr("tactus.broker.server.OpenAIChatBackend", lambda api_key=None: object())
    monkeypatch.setattr("ssl.SSLContext", lambda *_args, **_kwargs: FakeSSLContext())
    monkeypatch.setattr(runner, "_run_container", fake_run_container)

    result = await runner.run(source="main = Procedure { function() end }")

    assert result.status.value == "success"


@pytest.mark.asyncio
async def test_run_cleans_up_temp_dir_failure(monkeypatch, tmp_path: Path):
    runner = ContainerRunner(SandboxConfig())

    temp_dir = tmp_path / "workspace"
    temp_dir.mkdir()

    async def fake_run_container(*_args, **_kwargs):
        return ExecutionResult.success(result={"ok": True})

    monkeypatch.setattr(runner, "_ensure_sandbox_up_to_date", lambda **_kwargs: None)
    monkeypatch.setattr(container_runner_module.tempfile, "mkdtemp", lambda prefix: str(temp_dir))
    monkeypatch.setattr(runner, "_build_docker_command", lambda **_kwargs: ["docker"])
    monkeypatch.setattr(runner, "_run_container", fake_run_container)
    monkeypatch.setattr(
        container_runner_module.shutil,
        "rmtree",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    result = await runner.run(source="main = Procedure { function() end }")

    assert result.status.value == "success"


@pytest.mark.asyncio
async def test_run_logs_cleanup_failure(monkeypatch, tmp_path: Path, caplog):
    runner = ContainerRunner(SandboxConfig())

    temp_dir = tmp_path / "workspace"
    temp_dir.mkdir()
    cleanup_called = {"value": False}

    async def fake_run_container(*_args, **_kwargs):
        return ExecutionResult.success(result={"ok": True})

    def boom(*_args, **_kwargs):
        cleanup_called["value"] = True
        raise RuntimeError("boom")

    monkeypatch.setattr(runner, "_ensure_sandbox_up_to_date", lambda **_kwargs: None)
    monkeypatch.setattr(container_runner_module.tempfile, "mkdtemp", lambda prefix: str(temp_dir))
    monkeypatch.setattr(runner, "_build_docker_command", lambda **_kwargs: ["docker"])
    monkeypatch.setattr(runner, "_run_container", fake_run_container)
    monkeypatch.setattr(container_runner_module.shutil, "rmtree", boom)

    with caplog.at_level(logging.WARNING, logger="tactus.sandbox.container_runner"):
        result = await runner.run(source="main = Procedure { function() end }")

    assert result.status.value == "success"
    assert cleanup_called["value"] is True
    assert any("Failed to cleanup temp dir" in record.message for record in caplog.records)
