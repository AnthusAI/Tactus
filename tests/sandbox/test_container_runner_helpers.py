import logging
import sys
from pathlib import Path

import pytest

from tactus.sandbox.config import SandboxConfig
from tactus.sandbox.container_runner import ContainerRunner, SandboxUnavailableError
from tactus.sandbox.protocol import ExecutionResult, ExecutionStatus


def test_normalize_volume_spec_resolves_relative_paths(tmp_path):
    runner = ContainerRunner(SandboxConfig(mount_current_dir=False))
    base_dir = tmp_path / "base"
    base_dir.mkdir()

    normalized = runner._normalize_volume_spec("./data:/data:ro", base_dir=base_dir)

    expected = (base_dir / "data").resolve()
    assert normalized == f"{expected}:/data:ro"


def test_normalize_volume_spec_leaves_named_volume():
    runner = ContainerRunner(SandboxConfig(mount_current_dir=False))

    normalized = runner._normalize_volume_spec("cache:/data", base_dir=None)

    assert normalized == "cache:/data"


def test_normalize_volume_spec_handles_invalid_and_home_path(tmp_path, monkeypatch):
    runner = ContainerRunner(SandboxConfig(mount_current_dir=False))

    assert runner._normalize_volume_spec("invalid", base_dir=None) == "invalid"

    monkeypatch.setenv("HOME", str(tmp_path))
    normalized = runner._normalize_volume_spec("~/data:/data:rw", base_dir=None)
    assert normalized.startswith(str(tmp_path / "data"))


def test_normalize_volume_spec_relative_without_mode(tmp_path):
    runner = ContainerRunner(SandboxConfig(mount_current_dir=False))
    base_dir = tmp_path / "base"
    base_dir.mkdir()

    normalized = runner._normalize_volume_spec("./data:/data", base_dir=base_dir)

    expected = (base_dir / "data").resolve()
    assert normalized == f"{expected}:/data"


def test_build_docker_command_includes_expected_flags(tmp_path):
    mcp_path = tmp_path / "mcp"
    mcp_path.mkdir()
    (tmp_path / "tactus").mkdir()

    config = SandboxConfig(
        mount_current_dir=False,
        dev_mode=True,
        env={"FOO": "bar", "OPENAI_API_KEY": "secret"},
        volumes=["./data:/data:ro"],
    )
    runner = ContainerRunner(config)

    def fake_find_source_dir():
        return tmp_path

    runner._find_tactus_source_dir = fake_find_source_dir

    cmd = runner._build_docker_command(
        working_dir=tmp_path,
        mcp_servers_path=mcp_path,
        extra_env={"EXTRA": "1"},
        execution_id="abc123",
        callback_url="http://localhost/callback",
        volume_base_dir=tmp_path,
    )

    cmd_str = " ".join(cmd)
    assert "tactus-sandbox-abc123" in cmd_str
    assert "--env FOO=bar" in cmd_str
    assert "OPENAI_API_KEY" not in cmd_str
    assert "--env EXTRA=1" in cmd_str
    assert "--env TACTUS_CALLBACK_URL=http://localhost/callback" in cmd_str
    assert f"-v {mcp_path}:/mcp-servers:ro" in cmd_str

    normalized_volume = f"{(tmp_path / 'data').resolve()}:/data:ro"
    assert normalized_volume in cmd_str
    assert f"-v {tmp_path}/tactus:/app/tactus:ro" in cmd_str


def test_build_docker_command_handles_limits_and_dev_mode_missing_source(
    tmp_path, caplog, monkeypatch
):
    mcp_path = tmp_path / "mcp"
    mcp_path.mkdir()

    config = SandboxConfig(
        mount_current_dir=False,
        dev_mode=True,
        env={"OPENAI_API_KEY": "secret"},
    )
    config.limits.memory = "512m"
    config.limits.cpus = "1.5"
    runner = ContainerRunner(config)

    monkeypatch.setattr(runner, "_find_tactus_source_dir", lambda: None)

    with caplog.at_level(logging.WARNING):
        cmd = runner._build_docker_command(
            working_dir=tmp_path,
            mcp_servers_path=mcp_path,
            extra_env=None,
            execution_id="abc123",
            callback_url="http://localhost/callback",
            volume_base_dir=tmp_path,
        )

    cmd_str = " ".join(cmd)
    assert "--memory 512m" in cmd_str
    assert "--cpus 1.5" in cmd_str
    assert f"-v {mcp_path}:/mcp-servers:ro" in cmd_str
    assert "--env TACTUS_CALLBACK_URL=http://localhost/callback" in cmd_str
    assert any("Refusing to pass secret env var" in record.message for record in caplog.records)


def test_build_docker_command_skips_empty_limits(tmp_path):
    config = SandboxConfig(mount_current_dir=False)
    config.limits.memory = ""
    config.limits.cpus = ""
    runner = ContainerRunner(config)

    cmd = runner._build_docker_command(
        working_dir=tmp_path,
        mcp_servers_path=None,
        extra_env={"TACTUS_BROKER_SOCKET": "stdio"},
        execution_id="abc123",
        callback_url=None,
        volume_base_dir=tmp_path,
    )

    cmd_str = " ".join(cmd)
    assert "--memory" not in cmd_str
    assert "--cpus" not in cmd_str


def test_handle_container_stderr_raw_mode(capsys):
    config = SandboxConfig(mount_current_dir=False, env={"TACTUS_LOG_FORMAT": "raw"})
    runner = ContainerRunner(config)

    runner._handle_container_stderr("hello stderr\n")

    captured = capsys.readouterr()
    assert "hello stderr" in captured.err


def test_handle_container_stderr_empty_is_noop(capsys):
    config = SandboxConfig(mount_current_dir=False)
    runner = ContainerRunner(config)

    runner._handle_container_stderr("")

    captured = capsys.readouterr()
    assert captured.err == ""


def test_handle_container_stderr_parses_log_records(caplog):
    config = SandboxConfig(mount_current_dir=False)
    runner = ContainerRunner(config)

    stderr = (
        "2024-01-01 00:00:00,000 [INFO] demo.logger: hello\n"
        "Context: details\n"
        "fallback warning\n"
    )

    with caplog.at_level(logging.INFO):
        runner._handle_container_stderr(stderr)

    messages = [record.getMessage() for record in caplog.records]
    assert "hello\nContext: details" in messages
    assert any("fallback warning" in msg for msg in messages)


def test_ensure_sandbox_up_to_date_skips_on_env(monkeypatch):
    config = SandboxConfig(mount_current_dir=False)
    runner = ContainerRunner(config)

    class DummyDockerManager:
        def needs_rebuild(self, _version, _hash):
            pytest.fail("needs_rebuild should not be called when auto-rebuild is disabled")

    runner.docker_manager = DummyDockerManager()

    monkeypatch.setenv("TACTUS_AUTO_REBUILD_SANDBOX", "false")
    runner._ensure_sandbox_up_to_date()


def test_ensure_sandbox_up_to_date_raises_on_failed_build(monkeypatch, tmp_path):
    config = SandboxConfig(mount_current_dir=False)
    runner = ContainerRunner(config)

    class DummyDockerManager:
        def needs_rebuild(self, _version, _hash):
            return True

        def build_image(self, **_kwargs):
            return False, "nope"

    runner.docker_manager = DummyDockerManager()

    monkeypatch.setenv("TACTUS_AUTO_REBUILD_SANDBOX", "true")
    monkeypatch.setattr(
        "tactus.sandbox.container_runner.resolve_dockerfile_path",
        lambda _path: (Path("Dockerfile"), "source"),
    )
    monkeypatch.setattr(
        "tactus.sandbox.container_runner.calculate_source_hash",
        lambda _path: "hash",
    )

    with pytest.raises(RuntimeError):
        runner._ensure_sandbox_up_to_date()


def test_ensure_sandbox_up_to_date_pypi_no_rebuild(monkeypatch, caplog):
    config = SandboxConfig(mount_current_dir=False)
    runner = ContainerRunner(config)

    class DummyDockerManager:
        def needs_rebuild(self, _version, _hash):
            return False

        def build_image(self, **_kwargs):
            pytest.fail("build_image should not be called when no rebuild is needed")

    runner.docker_manager = DummyDockerManager()

    monkeypatch.setenv("TACTUS_AUTO_REBUILD_SANDBOX", "true")
    monkeypatch.setattr(
        "tactus.sandbox.container_runner.resolve_dockerfile_path",
        lambda _path: (Path("Dockerfile"), "pypi"),
    )

    with caplog.at_level(logging.DEBUG):
        runner._ensure_sandbox_up_to_date()

    assert any("No source tree detected" in record.message for record in caplog.records)
    assert any("Sandbox is up to date" in record.message for record in caplog.records)


def test_find_tactus_source_dir_handles_invalid_env_and_import(monkeypatch, tmp_path):
    runner = ContainerRunner(SandboxConfig(mount_current_dir=False))

    monkeypatch.setenv("TACTUS_DEV_PATH", str(tmp_path / "missing"))

    real_import = __import__

    def fake_import(name, *args, **kwargs):
        if name == "tactus":
            raise ImportError("nope")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)
    monkeypatch.chdir(tmp_path)

    assert runner._find_tactus_source_dir() is None


def test_find_tactus_source_dir_from_module_path(monkeypatch, tmp_path):
    runner = ContainerRunner(SandboxConfig(mount_current_dir=False))

    repo_root = tmp_path / "repo"
    (repo_root / "tactus").mkdir(parents=True)
    (repo_root / "pyproject.toml").write_text("", encoding="utf-8")
    module_path = repo_root / "tactus" / "__init__.py"
    module_path.write_text("", encoding="utf-8")

    class FakeModule:
        __file__ = str(module_path)

    monkeypatch.setitem(sys.modules, "tactus", FakeModule)

    assert runner._find_tactus_source_dir() == repo_root


def test_sandbox_unavailable_error_includes_reason():
    err = SandboxUnavailableError("daemon down")
    assert err.reason == "daemon down"
    assert "daemon down" in str(err)


def test_run_sync_wraps_asyncio(monkeypatch):
    runner = ContainerRunner(SandboxConfig(mount_current_dir=False))
    result = ExecutionResult.success(result={"ok": True})
    called = {}

    def fake_run(coro):
        called["coro"] = coro
        coro.close()
        return result

    monkeypatch.setattr("asyncio.run", fake_run)
    output = runner.run_sync(source="Procedure { function() return { ok = true } end }")

    assert output == result
    assert called["coro"] is not None


@pytest.mark.asyncio
async def test_run_returns_failure_for_invalid_transport(monkeypatch):
    config = SandboxConfig(mount_current_dir=False, broker_transport="invalid")
    runner = ContainerRunner(config)

    monkeypatch.setenv("TACTUS_AUTO_REBUILD_SANDBOX", "false")

    result = await runner.run(source='Agent "a" {}')

    assert isinstance(result, ExecutionResult)
    assert result.status == ExecutionStatus.ERROR
    assert result.error_type == "SandboxError"
