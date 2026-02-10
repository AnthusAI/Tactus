# Tactus LSP Server

Language Server Protocol server for Tactus AI workflow language.

## Installation

```bash
pip install tactus-lsp-server
```

## Usage

This package is automatically used by the Tactus VSCode extension.

To test manually:
```bash
tactus-lsp-server
# Server will listen on stdin/stdout for JSON-RPC messages
```

## Requirements

- Python 3.9+
- Tactus core package (`tactus>=0.39.0`)

## Features

- Real-time validation
- Code completions
- Hover documentation
- Semantic highlighting
- Signature help

## Development

To install for development:
```bash
cd tactus-lsp-server
pip install -e .
```

## License

MIT License - see LICENSE file in the root of the repository.
