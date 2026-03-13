#!/bin/bash
# Run tests the same way CI does
# -n0 disables xdist parallelization to avoid test isolation issues
cd "$(dirname "$0")"
python scripts/fetch_wikitext2.py
python3 -m poetry run pytest tests/ -v --tb=short -m "not integration" -n0 "$@"
