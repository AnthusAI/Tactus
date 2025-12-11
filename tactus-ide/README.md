# Tactus IDE

Full-featured IDE for editing Tactus DSL (`.tactus.lua`) files with instant feedback and intelligent code completion.

## Architecture

The Tactus IDE uses a **hybrid validation approach** for optimal performance:

```
┌─────────────────────────────────────────────────────────────┐
│ Frontend (React + Monaco Editor)                            │
│                                                             │
│  Layer 1: TypeScript Parser (< 10ms)                       │
│  ├─ Instant syntax validation                              │
│  ├─ Works offline                                           │
│  └─ ANTLR-generated from Lua.g4                            │
│                                                             │
│  Layer 2: LSP Client (300ms debounced)                     │
│  ├─ Semantic validation                                     │
│  ├─ Intelligent completions                                 │
│  └─ Hover documentation                                     │
└──────────────────┬──────────────────────────────────────────┘
                   │ WebSocket (Socket.IO)
┌──────────────────▼──────────────────────────────────────────┐
│ Backend (Flask + Python LSP)                                │
│  ├─ Semantic validation using TactusValidator              │
│  ├─ Context-aware completions                               │
│  ├─ Hover info from ProcedureRegistry                       │
│  └─ SSE for procedure execution (future)                    │
└─────────────────────────────────────────────────────────────┘
```

## Features

### Instant Feedback
- **Syntax errors appear immediately** (< 10ms via TypeScript parser)
- **Semantic errors after 300ms** (via Python LSP)
- **No lag, no waiting** for validation

### Language Intelligence
- **Autocomplete**: DSL functions, agent names, parameters
- **Hover documentation**: Agent configs, parameter types, output fields
- **Signature help**: Function parameter hints
- **Error highlighting**: Red squiggles for both syntax and semantic errors

### Offline Capable
- **Works without backend** for basic editing
- **TypeScript parser** provides syntax validation offline
- **Graceful degradation** when LSP unavailable

### Cross-Platform
- **Electron-ready** for desktop packaging
- **Web-based** for development
- **Standard technologies**: React, Monaco, Flask

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- npm

### Running the IDE

**Option 1: Use the startup script (recommended)**
```bash
cd tactus-ide
./start-dev.sh
```

**Option 2: Manual startup**
```bash
# Terminal 1: Start backend (port 5001)
cd tactus-ide/backend
pip install -r requirements.txt
python app.py

# Terminal 2: Start frontend (port 3000)
cd tactus-ide/frontend
npm install
npm run dev
```

Open http://localhost:3000 in your browser.

### Connection Status

The IDE shows connection status in the header:
- **● LSP Connected**: Backend is running, full features available
- **○ Offline Mode**: Backend unavailable, syntax validation still works

See [FIXES.md](FIXES.md) for recent improvements to connection handling and error management.

## Project Structure

```
tactus-ide/
├── backend/                    # Python LSP server
│   ├── app.py                  # Flask app with WebSocket
│   ├── lsp_server.py           # LSP protocol implementation
│   ├── tactus_lsp_handler.py   # Tactus-specific LSP logic
│   ├── test_lsp_server.py      # Backend tests
│   └── requirements.txt
│
└── frontend/                   # React + Monaco
    ├── src/
    │   ├── App.tsx             # Main app component
    │   ├── Editor.tsx          # Monaco editor with hybrid validation
    │   ├── LSPClient.ts        # LSP WebSocket client
    │   ├── TactusLanguage.ts   # Monaco language definition
    │   ├── main.tsx            # Entry point
    │   └── validation/         # TypeScript parser (ANTLR-generated)
    │       ├── generated/
    │       ├── TactusValidator.ts
    │       └── ...
    ├── index.html
    ├── vite.config.ts
    └── package.json
```

## Hybrid Validation Explained

### Why Two Parsers?

**TypeScript Parser (Client-Side):**
- Instant syntax validation (< 10ms)
- No network delay
- Works offline
- Reduces backend load

**Python LSP (Backend):**
- Semantic validation (cross-references, missing fields)
- Intelligent completions (context-aware)
- Hover documentation (from registry)
- Can integrate with runtime (future)

### How It Works

1. **User types** → TypeScript parser validates syntax instantly
2. **After 300ms** → LSP backend validates semantics
3. **User requests completion** → Both provide suggestions
4. **User hovers** → LSP shows documentation

### Benefits

- **Zero-latency feedback**: Syntax errors appear instantly
- **Smart features**: Completions know about your agents/parameters
- **Offline capable**: Basic editing works without internet
- **Scalable**: Backend only handles semantic requests

## Development

### Backend Development

```bash
cd tactus-ide/backend

# Install dependencies
pip install -r requirements.txt

# Run tests
pytest test_lsp_server.py

# Run server
python app.py
```

### Frontend Development

```bash
cd tactus-ide/frontend

# Install dependencies
npm install

# Run development server
npm run dev

# Run tests
npm test

# Run parser demo
npm run demo

# Build for production
npm run build
```

## Testing

### Backend Tests
```bash
cd tactus-ide/backend
pytest test_lsp_server.py
```

Tests cover:
- LSP protocol handlers
- Semantic validation
- Completions generation
- Hover information
- Error handling

### Frontend Tests
```bash
cd tactus-ide/frontend
npm test
```

Tests cover:
- TypeScript parser (12 tests)
- Syntax validation
- DSL extraction
- Example file validation

### Integration Testing

Test with real `.tactus.lua` files:
```bash
# Validate examples with TypeScript parser
cd tactus-ide/frontend
npm run demo

# Validate examples with Python parser
cd ../..
tactus validate examples/*.tactus.lua
```

## Future Enhancements

### Near-Term
- Multiple file tabs
- File tree explorer
- Improved error messages with quick fixes
- More intelligent completions

### Long-Term
- Procedure execution with live output (via SSE)
- Debugging features (breakpoints, step through)
- Git integration
- Electron packaging for desktop distribution
- AWS Amplify deployment option

## Electron Packaging

The IDE is designed for Electron:
- Backend runs as subprocess
- Frontend uses Electron's file system APIs
- IPC instead of HTTP for local communication
- No changes needed to core code

## AWS Amplify Deployment

For cloud deployment:
- Backend as Lambda functions
- SSE via API Gateway WebSocket
- File storage via S3
- Frontend served via CloudFront
- TypeScript parser still provides instant validation

## Technology Stack

### Frontend
- **React 18**: UI framework
- **Monaco Editor**: Code editor (VS Code's editor)
- **TypeScript**: Type-safe development
- **Vite**: Fast build tool
- **Socket.IO**: WebSocket communication

### Backend
- **Flask**: Web framework
- **Flask-SocketIO**: WebSocket support
- **Python 3.11+**: Language runtime
- **ANTLR4**: Parser generation
- **Redis**: SSE support (future)

### Shared
- **ANTLR Grammar**: `Lua.g4` generates both parsers
- **LSP Protocol**: Standard language server protocol
- **JSON-RPC 2.0**: LSP message format


