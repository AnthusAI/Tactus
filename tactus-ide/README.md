# Tactus IDE

A sophisticated code editor for Tactus workflow files with integrated validation, execution, and AI assistance.

## Quick Start

### Development Mode (Recommended for Development)

**One command to rule them all:**

```bash
make dev-ide
```

This starts:
- ✨ Backend with **auto-reload** on Python changes (using `watchmedo`)
- 🔥 Frontend with **hot module replacement** on TypeScript/React changes (using Vite HMR)
- 🚀 Both servers in one terminal with proper cleanup on Ctrl+C

**What you get:**
- Edit Python backend → server auto-restarts (1-2 seconds)
- Edit React components → instant hot reload (< 100ms)
- Edit CSS/Tailwind → instant update
- No manual restarts needed!

Open http://localhost:3000 in your browser.

### Production Mode

```bash
# Build and run the production version
tactus ide
```

This serves the pre-built frontend from `dist/` and is what end-users will use.

## Architecture

### Hybrid Validation System

The IDE uses a two-layer validation approach:

**Layer 1: TypeScript Parser (Client-Side)**
- ANTLR-generated from same `Lua.g4` grammar as Python parser
- Instant syntax validation (< 10ms)
- Runs in browser, no backend needed
- Works offline

**Layer 2: Python LSP (Backend)**
- Uses existing `TactusValidator` from `tactus/validation/`
- Semantic validation and intelligence
- Debounced (300ms) to reduce load
- Provides completions, hover, signature help

### Tech Stack

**Frontend:**
- React + TypeScript
- Monaco Editor (same as VS Code)
- Shadcn UI + Tailwind CSS
- Lucide React icons
- Vite (dev server + build tool)

**Backend:**
- Python Flask
- Language Server Protocol (LSP)
- WebSocket for real-time communication
- Tactus runtime integration

**Desktop:**
- Electron wrapper (optional)
- Native menus and file dialogs
- IPC bridge for command dispatch

## Development Workflow

### Making Changes

1. **Start dev mode:**
   ```bash
   make dev-ide
   ```

2. **Edit files:**
   - Frontend: `tactus-ide/frontend/src/**/*`
   - Backend: `tactus/ide/server.py` or `tactus-ide/backend/app.py`
   - Components: `tactus-ide/frontend/src/components/**/*`

3. **See changes instantly:**
   - Frontend changes appear immediately (HMR)
   - Backend changes trigger auto-restart (1-2 seconds)

4. **No manual steps needed!**

### Building for Production

```bash
make build-ide
```

This creates optimized production build in `tactus-ide/frontend/dist/`.

### Running Tests

```bash
# All tests
make test

# Parser tests specifically
make test-parsers
```

## Project Structure

```
tactus-ide/
├── dev.sh                    # Development mode script (auto-reload)
├── frontend/
│   ├── src/
│   │   ├── App.tsx          # Main IDE layout
│   │   ├── Editor.tsx       # Monaco editor with LSP
│   │   ├── components/
│   │   │   ├── FileTree.tsx # File browser sidebar
│   │   │   ├── ChatSidebar.tsx # AI chat interface
│   │   │   └── ui/          # Shadcn UI components
│   │   ├── commands/
│   │   │   └── registry.ts  # Centralized command system
│   │   └── validation/
│   │       └── generated/   # TypeScript parser (ANTLR)
│   ├── package.json
│   └── vite.config.ts       # Vite configuration
└── backend/
    ├── app.py               # Flask API server
    └── requirements.txt
```

## Features

### File Management
- Open folder as workspace (like VS Code)
- File tree with `.tac` highlighting
- Workspace-sandboxed file operations (no path traversal)
- Auto-open `examples/` folder on first launch

### Code Editing
- Monaco editor (VS Code engine)
- Syntax highlighting for Lua
- Instant syntax validation (TypeScript parser)
- Semantic validation via LSP
- Auto-completion and hover info

### Execution
- Validate button (syntax + semantic checks)
- Run button (execute procedure)
- Validate + Run (combined)
- Results displayed in bottom drawer

### UI/UX
- Collapsible left sidebar (file tree)
- Collapsible right sidebar (AI chat)
- Bottom drawer (metrics/results)
- Top menu bar (consistent with Electron menus)
- Dark mode support
- Lucide icons throughout

### Command System
- Centralized command registry
- Works in both browser and Electron
- Keyboard shortcuts
- Native menu integration (Electron)
- In-app menu bar (browser)

## Requirements

### Development
- Python 3.11+
- Node.js 18+
- `watchdog[watchmedo]` (auto-installed by `make dev-ide`)

### Production
- Python 3.11+
- Pre-built frontend (included in package)

### Parser Generation (Optional)
- Docker (only needed if modifying Lua grammar)

## Troubleshooting

### Port Already in Use

The dev script auto-detects available ports:
- Backend tries 5001, 5002, 5003, etc.
- Frontend tries 3000, 3001, 3002, etc.
- Multiple instances can run simultaneously

### Backend Not Auto-Reloading

Make sure `watchdog` is installed:
```bash
pip install 'watchdog[watchmedo]'
```

### Frontend Not Hot-Reloading

Check that Vite dev server is running (not production build):
```bash
# Should see "VITE" in output, not "Serving static files"
make dev-ide
```

### Changes Not Appearing in `tactus ide`

The `tactus ide` command serves pre-built files. You need to rebuild:
```bash
make build-ide
```

Or use development mode instead:
```bash
make dev-ide
```

## Contributing

1. Use `make dev-ide` for development
2. Test changes with `make test`
3. Build production version with `make build-ide`
4. Verify with `tactus ide`

## License

See LICENSE file in project root.








