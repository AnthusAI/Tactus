import subprocess
import sys


def test_core_runtime_import_does_not_load_dspy_or_litellm():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; sys.modules['dspy'] = None; sys.modules['litellm'] = None; "
            "from tactus.core.runtime import TactusRuntime; "
            "assert TactusRuntime.__name__ == 'TactusRuntime'",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
