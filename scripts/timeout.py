#!/usr/bin/env python3
"""
Run a command with a hard timeout.

This repo targets environments where `timeout` may not be available (e.g. macOS),
but we still want deterministic bounds on long-running or stalled commands.

Usage:
  scripts/timeout.py 300 pytest tests/ -x

Exit codes:
  - Propagates the child process exit code on normal completion
  - 124 on timeout (matching GNU coreutils `timeout`)
"""

from __future__ import annotations

import subprocess
import sys
from typing import Sequence


def _usage() -> str:
    return "Usage: scripts/timeout.py <seconds> <command...>"


def main(argv: Sequence[str]) -> int:
    if len(argv) < 3:
        print(_usage(), file=sys.stderr)
        return 2

    try:
        seconds = float(argv[1])
    except ValueError:
        print(f"Invalid seconds value: {argv[1]!r}\n{_usage()}", file=sys.stderr)
        return 2

    cmd = list(argv[2:])
    try:
        completed = subprocess.run(cmd, timeout=seconds)
        return completed.returncode
    except subprocess.TimeoutExpired:
        print(f"✗ Timed out after {seconds:.0f}s: {' '.join(cmd)}", file=sys.stderr)
        return 124


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

