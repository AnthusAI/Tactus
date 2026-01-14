#!/bin/bash
# Run tests the same way CI does
cd "$(dirname "$0")"
pytest tests/ -v --tb=short -m "not integration" "$@"
