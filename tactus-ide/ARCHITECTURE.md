# Tactus IDE Architecture

## Overview

The Tactus IDE uses a **hybrid validation architecture** combining client-side and server-side validation for optimal performance and user experience.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          Browser (Client)                           │
│                      http://localhost:3000                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌───────────────────────────────────────────────────────────┐    │
│  │ React Application                                         │    │
│  │                                                           │    │
│  │  ┌─────────────────────────────────────────────────┐     │    │
│  │  │ Monaco Editor                                   │     │    │
│  │  │ - Code editing                                  │     │    │
│  │  │ - Syntax highlighting                           │     │    │
│  │  │ - Error markers                                 │     │    │
│  │  │ - Auto-completion UI                            │     │    │
│  │  └─────────────────────────────────────────────────┘     │    │
│  │                                                           │    │
│  │  ┌─────────────────────────────────────────────────┐     │    │
│  │  │ Layer 1: TypeScript Parser (Client-Side)       │     │    │
│  │  │                                                 │     │    │
│  │  │ - ANTLR-generated from Lua.g4                  │     │    │
│  │  │ - Instant syntax validation (< 10ms)           │     │    │
│  │  │ - Works offline                                 │     │    │
│  │  │ - No backend required                           │     │    │
│  │  │ - Runs in browser                               │     │    │
│  │  │                                                 │     │    │
│  │  │ Input: Code string                             │     │    │
│  │  │ Output: Syntax errors with locations           │     │    │
│  │  └─────────────────────────────────────────────────┘     │    │
│  │                                                           │    │
│  │  ┌─────────────────────────────────────────────────┐     │    │
│  │  │ Layer 2: LSP Client (Semantic)                 │     │    │
│  │  │                                                 │     │    │
│  │  │ - Socket.IO WebSocket client                   │     │    │
│  │  │ - Debounced validation (300ms)                 │     │    │
│  │  │ - Semantic error detection                      │     │    │
│  │  │ - Context-aware completions                     │     │    │
│  │  │ - Hover documentation                           │     │    │
│  │  │ - Graceful offline fallback                     │     │    │
│  │  │                                                 │     │    │
│  │  │ Input: Code + cursor position                  │     │    │
│  │  │ Output: Semantic errors + completions          │     │    │
│  │  └─────────────────────────────────────────────────┘     │    │
│  │                                                           │    │
│  └───────────────────────────────────────────────────────────┘    │
│                                                                     │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                           │ WebSocket (Socket.IO)
                           │ ws://localhost:5001/socket.io
                           │ Protocol: JSON-RPC 2.0
                           │
┌──────────────────────────▼──────────────────────────────────────────┐
│                      Backend (Server)                               │
│                   http://localhost:5001                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌───────────────────────────────────────────────────────────┐    │
│  │ Flask Application                                         │    │
│  │                                                           │    │
│  │  ┌─────────────────────────────────────────────────┐     │    │
│  │  │ HTTP Endpoints                                  │     │    │
│  │  │                                                 │     │    │
│  │  │ GET  /health        → Health check             │     │    │
│  │  │ GET  /api/file      → Read file                │     │    │
│  │  │ POST /api/file      → Write file               │     │    │
│  │  └─────────────────────────────────────────────────┘     │    │
│  │                                                           │    │
│  │  ┌─────────────────────────────────────────────────┐     │    │
│  │  │ WebSocket Handlers (Socket.IO)                 │     │    │
│  │  │                                                 │     │    │
│  │  │ Event: connect      → Client connected         │     │    │
│  │  │ Event: disconnect   → Client disconnected      │     │    │
│  │  │ Event: lsp          → LSP request/response     │     │    │
│  │  │ Event: lsp_notification → LSP notification     │     │    │
│  │  └─────────────────────────────────────────────────┘     │    │
│  │                                                           │    │
│  │  ┌─────────────────────────────────────────────────┐     │    │
│  │  │ LSP Server                                      │     │    │
│  │  │                                                 │     │    │
│  │  │ - JSON-RPC 2.0 protocol handler                │     │    │
│  │  │ - Method routing                                │     │    │
│  │  │ - Document lifecycle management                 │     │    │
│  │  │                                                 │     │    │
│  │  │ Methods:                                        │     │    │
│  │  │ - initialize                                    │     │    │
│  │  │ - textDocument/didOpen                         │     │    │
│  │  │ - textDocument/didChange                       │     │    │
│  │  │ - textDocument/didClose                        │     │    │
│  │  │ - textDocument/completion                      │     │    │
│  │  │ - textDocument/hover                           │     │    │
│  │  │ - textDocument/signatureHelp                   │     │    │
│  │  └─────────────────────────────────────────────────┘     │    │
│  │                                                           │    │
│  │  ┌─────────────────────────────────────────────────┐     │    │
│  │  │ Tactus LSP Handler                             │     │    │
│  │  │                                                 │     │    │
│  │  │ - Uses TactusValidator for validation          │     │    │
│  │  │ - Generates completions from registry          │     │    │
│  │  │ - Provides hover documentation                  │     │    │
│  │  │ - Semantic error detection                      │     │    │
│  │  │                                                 │     │    │
│  │  │ Components:                                     │     │    │
│  │  │ - TactusValidator (from tactus package)        │     │    │
│  │  │ - ProcedureRegistry (DSL functions)            │     │    │
│  │  │ - CompletionProvider (context-aware)           │     │    │
│  │  └─────────────────────────────────────────────────┘     │    │
│  │                                                           │    │
│  └───────────────────────────────────────────────────────────┘    │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## Data Flow

### 1. Syntax Validation (Instant)

```
User types code
      │
      ▼
┌─────────────────┐
│ Monaco Editor   │
│ (onChange)      │
└────────┬────────┘
         │
         │ Code string
         ▼
┌─────────────────┐
│ TypeScript      │
│ Parser          │◄─── ANTLR-generated from Lua.g4
│ (TactusValidator│
│  .validate())   │
└────────┬────────┘
         │
         │ Syntax errors
         ▼
┌─────────────────┐
│ Monaco Editor   │
│ (setModelMarkers│      Red squiggles appear
│  'tactus-syntax'│      instantly (< 10ms)
│  markers)       │
└─────────────────┘
```

### 2. Semantic Validation (Debounced)

```
User types code
      │
      ▼
┌─────────────────┐
│ Monaco Editor   │
│ (onChange)      │
└────────┬────────┘
         │
         │ Wait 300ms (debounce)
         ▼
┌─────────────────┐
│ LSP Client      │
│ (didChange)     │
└────────┬────────┘
         │
         │ WebSocket: textDocument/didChange
         ▼
┌─────────────────┐
│ LSP Server      │
│ (handle_message)│
└────────┬────────┘
         │
         │ Parse and validate
         ▼
┌─────────────────┐
│ Tactus LSP      │
│ Handler         │◄─── Uses TactusValidator
│ (validate)      │     from tactus package
└────────┬────────┘
         │
         │ Semantic errors
         ▼
┌─────────────────┐
│ LSP Server      │
│ (emit)          │
└────────┬────────┘
         │
         │ WebSocket: textDocument/publishDiagnostics
         ▼
┌─────────────────┐
│ LSP Client      │
│ (onDiagnostics) │
└────────┬────────┘
         │
         │ Semantic errors
         ▼
┌─────────────────┐
│ Monaco Editor   │
│ (setModelMarkers│      Blue squiggles appear
│  'tactus-       │      after 300ms
│   semantic')    │
└─────────────────┘
```

### 3. Auto-Completion

```
User triggers completion (Ctrl+Space)
      │
      ▼
┌─────────────────┐
│ Monaco Editor   │
│ (onCompletion)  │
└────────┬────────┘
         │
         │ Cursor position
         ▼
┌─────────────────┐
│ LSP Client      │
│ (requestCompletions)
└────────┬────────┘
         │
         │ WebSocket: textDocument/completion
         ▼
┌─────────────────┐
│ LSP Server      │
│ (handle_message)│
└────────┬────────┘
         │
         │ Get completions
         ▼
┌─────────────────┐
│ Tactus LSP      │
│ Handler         │◄─── Uses ProcedureRegistry
│ (get_completions│     for DSL functions
└────────┬────────┘
         │
         │ Completion items
         ▼
┌─────────────────┐
│ LSP Server      │
│ (emit)          │
└────────┬────────┘
         │
         │ WebSocket: completion items
         ▼
┌─────────────────┐
│ LSP Client      │
│ (resolve)       │
└────────┬────────┘
         │
         │ Completion items
         ▼
┌─────────────────┐
│ Monaco Editor   │
│ (show           │      Completion popup
│  suggestions)   │      appears
└─────────────────┘
```

## Component Details

### Frontend Components

#### 1. App.tsx
- Main application container
- File management (open/save)
- Menu bar
- Editor container

#### 2. Editor.tsx
- Monaco editor wrapper
- Hybrid validation coordinator
- Connection status display
- Lifecycle management

#### 3. LSPClient.ts
- WebSocket client (Socket.IO)
- JSON-RPC 2.0 protocol
- Connection management
- Error handling

#### 4. TactusValidator.ts
- TypeScript parser wrapper
- Syntax validation
- Error extraction
- Offline validation

#### 5. TactusLanguage.ts
- Monaco language registration
- Syntax highlighting
- Theme definition
- Basic completions

### Backend Components

#### 1. app.py
- Flask application
- WebSocket server (Socket.IO)
- HTTP endpoints
- Request routing

#### 2. lsp_server.py
- LSP protocol implementation
- JSON-RPC 2.0 handler
- Method routing
- Document lifecycle

#### 3. tactus_lsp_handler.py
- Tactus-specific logic
- Semantic validation
- Completion generation
- Hover documentation

## Error Handling

### Client-Side

```
┌─────────────────┐
│ User Action     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Try/Catch       │
│ Block           │
└────────┬────────┘
         │
         ├─ Success → Continue
         │
         └─ Error
              │
              ▼
         ┌─────────────────┐
         │ Console.warn()  │  Not console.error()
         │ "LSP connection │  to avoid alarming
         │  error"         │  users
         └────────┬────────┘
                  │
                  ▼
         ┌─────────────────┐
         │ Graceful        │  IDE continues
         │ Degradation     │  working in
         │ (Offline Mode)  │  offline mode
         └─────────────────┘
```

### Server-Side

```
┌─────────────────┐
│ LSP Request     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Try/Catch       │
│ Block           │
└────────┬────────┘
         │
         ├─ Success → Return result
         │
         └─ Error
              │
              ▼
         ┌─────────────────┐
         │ Logger.error()  │  Log to console
         │ with details    │  for debugging
         └────────┬────────┘
                  │
                  ▼
         ┌─────────────────┐
         │ JSON-RPC Error  │  Return error
         │ Response        │  to client
         │ (code: -32603)  │
         └─────────────────┘
```

## Connection States

### State Machine

```
┌─────────────┐
│ Disconnected│◄────────┐
└──────┬──────┘         │
       │                │
       │ connect()      │ disconnect()
       │                │
       ▼                │
┌─────────────┐         │
│ Connecting  │         │
└──────┬──────┘         │
       │                │
       │ connected      │ error
       │                │
       ▼                │
┌─────────────┐         │
│ Connected   │─────────┤
└──────┬──────┘         │
       │                │
       │ initialize()   │
       │                │
       ▼                │
┌─────────────┐         │
│ Ready       │─────────┘
└─────────────┘
```

### UI Indicators

```
┌────────────────────────────────────────────────────┐
│ Tactus IDE    ● LSP Connected    Hybrid Validation│  ← Connected
└────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────┐
│ Tactus IDE    ○ Offline Mode     Hybrid Validation│  ← Disconnected
└────────────────────────────────────────────────────┘
```

## Performance Characteristics

### Syntax Validation (TypeScript)
- **Latency**: < 10ms
- **Throughput**: 100+ validations/second
- **Memory**: ~5MB per document
- **CPU**: Minimal (single-threaded)

### Semantic Validation (LSP)
- **Latency**: 300ms (debounced)
- **Throughput**: 3-4 validations/second
- **Memory**: ~20MB per document
- **CPU**: Moderate (Python interpreter)

### Network
- **Protocol**: WebSocket (Socket.IO)
- **Payload**: JSON-RPC 2.0 (~1-10KB)
- **Latency**: < 5ms (localhost)
- **Reconnection**: Automatic with exponential backoff

## Security Considerations

### Client-Side
- No sensitive data in localStorage
- CORS enabled for localhost only
- WebSocket origin validation
- No eval() or dynamic code execution

### Server-Side
- File operations restricted to project directory
- No shell command execution
- Input validation on all endpoints
- Error messages don't leak system info

## Future Enhancements

### Near-Term
- [ ] Multiple file tabs
- [ ] File tree explorer
- [ ] Quick fixes (code actions)
- [ ] Refactoring support

### Long-Term
- [ ] Procedure execution with live output
- [ ] Debugging features (breakpoints, step through)
- [ ] Git integration
- [ ] Electron packaging
- [ ] Cloud deployment (AWS Amplify)

## Technology Stack

### Frontend
- **React 18**: UI framework
- **Monaco Editor**: Code editor
- **TypeScript**: Type safety
- **Vite**: Build tool
- **Socket.IO Client**: WebSocket
- **ANTLR4 Runtime**: Parser

### Backend
- **Flask**: Web framework
- **Flask-SocketIO**: WebSocket
- **Python 3.11+**: Runtime
- **ANTLR4**: Parser generation
- **Tactus**: DSL validation

### Shared
- **ANTLR Grammar**: Lua.g4
- **LSP Protocol**: JSON-RPC 2.0
- **WebSocket**: Socket.IO

---

**Last Updated:** 2025-12-11  
**Version:** 1.0.0











