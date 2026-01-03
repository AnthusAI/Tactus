# Tactus IDE Backend

## Architecture Clarification

**Important:** The actual backend server is located at `tactus/ide/server.py`, not in this directory.

This directory contains supporting modules used by the backend server:

- `lsp_server.py` - LSP protocol implementation (JSON-RPC message handling)
- `tactus_lsp_handler.py` - LSP handler for Tactus validation and intelligence
- `logging_capture.py` - Event collection for streaming execution
- `events.py` - Event models for SSE streaming

## The Backend Server

The Flask backend server is at:
```
tactus/ide/server.py
```

It's integrated into the main `tactus` package so it can be run as:
```bash
python -m tactus.ide.server
```

Or via the development script:
```bash
make dev-ide
```

## Why This Structure?

The backend server is in `tactus/ide/` (not `tactus-ide/backend/`) because:

1. **Package Integration**: It needs to import from `tactus.core`, `tactus.validation`, etc.
2. **Distribution**: It's part of the installed `tactus` package
3. **Simplicity**: One backend server, not multiple versions

The modules in this directory (`tactus-ide/backend/`) are imported by the server but don't run independently.

## Development

When developing the IDE backend:

1. Edit `tactus/ide/server.py` for API endpoints and server logic
2. Edit files in this directory for LSP protocol and supporting functionality
3. Run `make dev-ide` to test changes with auto-reload

The dev script watches both directories and auto-restarts on changes.
