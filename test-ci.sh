#!/bin/bash
# Run tests the same way CI does
# -n0 disables xdist parallelization to avoid test isolation issues
cd "$(dirname "$0")"
pytest tests/ -v --tb=short -m "not integration" -n0 "$@"
