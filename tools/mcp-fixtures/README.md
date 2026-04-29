# MCP Fixtures Environment

This directory contains an isolated Python dependency environment for MCP test fixtures.

Why this exists:
- `fastmcp` currently requires `python-dotenv>=1.1.0`
- root `litellm` security-fixed versions require `python-dotenv==1.0.1`
- keeping `fastmcp` outside the root lock avoids resolver conflicts and lets root security remediation proceed

Usage:
```bash
cd tools/mcp-fixtures
python3 -m poetry install
python3 -m poetry run python -c "import fastmcp; print(fastmcp.__version__)"
```

The root project should not depend on this environment for standard runtime/release installs.
