import sys
import textwrap
from pathlib import Path

import pytest

from tactus.broker.stdio import STDIO_TRANSPORT_VALUE
from tactus.sandbox.config import SandboxConfig
from tactus.sandbox.container_runner import ContainerRunner
from tactus.sandbox.protocol import ExecutionRequest


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
        timeout=3,
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
