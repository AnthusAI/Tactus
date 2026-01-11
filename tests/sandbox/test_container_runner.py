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
    assert cmd[network_idx + 1] == "none"


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
