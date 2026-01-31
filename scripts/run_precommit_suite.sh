#!/usr/bin/env bash
set -euo pipefail

# Run the project's full pre-commit suite with per-command timeouts so the
# runner can't stall indefinitely on a "landmine" test.
#
# This script is intended to mirror GitHub Actions CI as closely as possible.
# Keep the command list and flags aligned with .github/workflows/release.yml.
#
# Default timeout per command is 300 seconds (5 minutes). Override via:
#   TACTUS_CMD_TIMEOUT_SECONDS=600 scripts/run_precommit_suite.sh
#
# Pytest can legitimately take longer than the other commands, so its command
# timeout is configurable separately:
#   TACTUS_PYTEST_CMD_TIMEOUT_SECONDS=900 scripts/run_precommit_suite.sh

TIMEOUT_SECONDS="${TACTUS_CMD_TIMEOUT_SECONDS:-300}"
PYTEST_CMD_TIMEOUT_SECONDS="${TACTUS_PYTEST_CMD_TIMEOUT_SECONDS:-900}"
TIMEOUT="scripts/timeout.py"

# Prefer an explicitly provided interpreter, otherwise try the repo's typical env.
PYTHON_BIN="${TACTUS_PYTHON_BIN:-}"
if [[ -z "${PYTHON_BIN}" ]]; then
  if [[ -x "/opt/anaconda3/envs/py311/bin/python" ]]; then
    PYTHON_BIN="/opt/anaconda3/envs/py311/bin/python"
  elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
  else
    PYTHON_BIN="python3"
  fi
fi

BIN_DIR="$(dirname "${PYTHON_BIN}")"

PYTEST="${BIN_DIR}/pytest"
BEHAVE="${BIN_DIR}/behave"
RUFF="${BIN_DIR}/ruff"
BLACK="${BIN_DIR}/black"

if [[ ! -x "${PYTEST}" ]]; then PYTEST="${PYTHON_BIN} -m pytest"; fi
if [[ ! -x "${BEHAVE}" ]]; then BEHAVE="${PYTHON_BIN} -m behave"; fi
if [[ ! -x "${RUFF}" ]]; then RUFF="${PYTHON_BIN} -m ruff"; fi
if [[ ! -x "${BLACK}" ]]; then BLACK="${PYTHON_BIN} -m black"; fi

run() {
  echo "→ $*"
  "$PYTHON_BIN" "$TIMEOUT" "$TIMEOUT_SECONDS" "$@"
  echo "✓ $*"
}

run_pytest() {
  echo "→ $*"
  "$PYTHON_BIN" "$TIMEOUT" "$PYTEST_CMD_TIMEOUT_SECONDS" "$@"
  echo "✓ $*"
}

run ${RUFF} check tactus/ tests/ features/steps/
run ${BLACK} --check tactus/ tests/ features/steps/
run_pytest ${PYTEST} tests/ -v --tb=short -m "not integration" -n0
run ${BEHAVE}
run tactus stdlib test
