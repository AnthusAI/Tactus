import os
import subprocess
import sys
from pathlib import Path

import pytest

import tactus
from tactus.sandbox.docker_manager import DockerManager, is_docker_available

pytestmark = [pytest.mark.docker, pytest.mark.integration]


def test_docker_sandbox_smoke(tmp_path: Path) -> None:
    """
    Opt-in Docker sandbox smoke test.

    This is skipped by default and only runs when explicitly enabled via:
      TACTUS_RUN_DOCKER_TESTS=1 pytest -m docker
    """
    if os.environ.get("TACTUS_RUN_DOCKER_TESTS") != "1":
        pytest.skip("Set TACTUS_RUN_DOCKER_TESTS=1 to run Docker sandbox tests")

    available, reason = is_docker_available()
    if not available:
        pytest.skip(f"Docker not available: {reason}")

    manager = DockerManager()
    if not manager.image_exists():
        pytest.skip(
            f"Sandbox image not built ({manager.full_image_name}). "
            "Run: tactus sandbox rebuild --force"
        )

    image_version = manager.get_image_version()
    expected_version = getattr(tactus, "__version__", None)
    if expected_version and image_version and image_version != expected_version:
        pytest.skip(
            f"Sandbox image version mismatch ({manager.full_image_name} is v{image_version}, "
            f"expected v{expected_version}). Run: tactus sandbox rebuild --force"
        )
    if image_version is None:
        pytest.skip(
            f"Sandbox image missing tactus.version label ({manager.full_image_name}). "
            "Run: tactus sandbox rebuild --force"
        )

    workflow_file = tmp_path / "smoke.tac"
    workflow_file.write_text(
        """Procedure {
    input = {},
    output = { ok = field.boolean{required = true} },
    function(input)
        return { ok = true }
    end
}
"""
    )

    isolated_home = tmp_path / "home"
    isolated_home.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["HOME"] = str(isolated_home)
    env["XDG_CONFIG_HOME"] = str(isolated_home)
    env.pop("OPENAI_API_KEY", None)

    repo_root = Path(__file__).resolve().parents[2]
    cmd = [
        sys.executable,
        "-m",
        "tactus.cli.app",
        "run",
        str(workflow_file),
        "--sandbox",
        "--sandbox-broker",
        "stdio",
        "--verbose",
    ]
    result = subprocess.run(
        cmd,
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )

    combined_output = (result.stdout or "") + "\n" + (result.stderr or "")
    if result.returncode != 0:
        raise AssertionError(
            f"Docker sandbox smoke test failed (exit={result.returncode}).\n\n"
            f"Command: {' '.join(cmd)}\n\n"
            f"Output:\n{combined_output}"
        )

    assert "procedure completed successfully" in combined_output.lower()
    assert "--network none" in combined_output.lower()
