# Tactus IDE Backend

Flask-based LSP server providing semantic language intelligence for the Tactus IDE.

## Architecture

The backend focuses on **semantic validation** and intelligence features.
Syntax validation is handled client-side by the TypeScript parser for instant feedback.

## Features

- **Language Server Protocol (LSP)**: Semantic language support
- **ANTLR-based validation**: Uses Tactus parser for full validation
- **SSE support**: Server-Sent Events for procedure execution output (future)
- **File operations**: Read/write `.tac` files

## Prerequisites

- **Python 3.11+** (required for Tactus package)

Check your version:
```bash
python --version  # Should be 3.11 or higher
```

## Running

```bash
# Install dependencies
pip install -r requirements.txt

# Install Tactus package (from project root)
cd ../..
pip install -e .

# Run the server
cd tactus-ide/backend
python app.py  # Starts on port 5001 (5000 is used by macOS AirPlay)
```

**Note**: If you get a Python version error, see the [GETTING_STARTED.md](../GETTING_STARTED.md#troubleshooting) guide for instructions on setting up Python 3.11+.

## LSP Capabilities

### Semantic Validation
- Missing required fields (e.g., agent without provider)
- Cross-reference errors (e.g., undefined agent referenced)
- Type mismatches
- Duplicate declarations

### Completions
- Context-aware suggestions based on parsed registry
- Agent names when typing in procedure
- Parameter names in agent config
- Tool names from agent tools list

### Hover
- Agent configuration details
- Parameter types and defaults
- Output field definitions
- Documentation links

### Signature Help
- Function parameter hints for DSL functions
- Expected config fields for agents, parameters, outputs

## Integration

The backend uses the existing Tactus validation infrastructure:
- `tactus.validation.validator.TactusValidator`
- `tactus.core.registry.ProcedureRegistry`
- ANTLR-generated parser from `tactus/validation/generated/`

## Hybrid Validation

The backend assumes syntax is already validated client-side:
- Client sends only semantically meaningful changes
- Backend focuses on cross-references and context
- Reduces load and latency
- Graceful degradation if backend unavailable











