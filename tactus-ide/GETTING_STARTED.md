# Getting Started with Tactus IDE

This guide will help you get the Tactus IDE up and running.

## What is Tactus IDE?

Tactus IDE is a desktop application for editing Tactus DSL (`.tactus.lua`) files with:
- **Instant syntax validation** (< 10ms)
- **Intelligent code completion**
- **Hover documentation**
- **Monaco Editor** (same as VS Code)

## Prerequisites

- **Python 3.11+** (required for Tactus package)
- **Node.js 18+** (for frontend)
- **npm** (comes with Node.js)

**Check your Python version:**
```bash
python --version  # Should be 3.11 or higher
```

If you have Python 3.9 or 3.10, you'll need to upgrade or use a virtual environment with Python 3.11+.

## Quick Start (5 minutes)

### Step 1: Install Backend Dependencies

```bash
cd tactus-ide/backend
pip install -r requirements.txt

# Install Tactus package (requires Python 3.11+)
cd ../..
pip install -e .
```

### Step 2: Install Frontend Dependencies

```bash
cd tactus-ide/frontend
npm install
```

### Step 3: Start the Backend

```bash
cd tactus-ide/backend
python app.py
```

You should see:
```
Starting Tactus IDE Backend on port 5001
```

**Note**: We use port 5001 instead of 5000 because macOS AirPlay Receiver uses port 5000 by default.

### Step 4: Start the Frontend

In a new terminal:

```bash
cd tactus-ide/frontend
npm run dev
```

You should see:
```
VITE ready in XXX ms
➜  Local:   http://localhost:3000/
```

### Step 5: Open the IDE

Open http://localhost:3000 in your browser.

You'll see the Tactus IDE with:
- Monaco editor with example code
- Syntax highlighting
- Real-time validation
- LSP connection indicator

## Try It Out

### Test Instant Validation

1. In the editor, delete a closing brace `}`
2. **Notice**: Red squiggle appears **instantly** (TypeScript parser)
3. Add the brace back
4. **Notice**: Error disappears immediately

### Test Semantic Validation

1. Delete the `provider = "openai"` line from an agent
2. **Wait 300ms**
3. **Notice**: Error appears about missing provider (Python LSP)

### Test Autocomplete

1. Type `ag` and press Ctrl+Space
2. **Notice**: Completion suggestions appear
3. Select `agent` and press Enter
4. **Notice**: Full agent template is inserted

### Test Hover

1. Hover over an agent name
2. **Notice**: Documentation appears showing agent configuration

### Open a File

1. Click "Open File" button
2. Enter path: `../../examples/hello-world.tactus.lua`
3. **Notice**: File loads and is validated

### Save a File

1. Make changes to the code
2. Click "Save File" button
3. File is saved to disk

## Understanding Hybrid Validation

The IDE uses **two validation layers**:

### Layer 1: TypeScript Parser (Instant)
- **Speed**: < 10ms
- **Scope**: Syntax only
- **Works**: Offline
- **Shows**: Missing braces, parentheses, invalid Lua syntax

### Layer 2: Python LSP (Semantic)
- **Speed**: 50-200ms (debounced 300ms)
- **Scope**: Semantics and intelligence
- **Requires**: Backend connection
- **Shows**: Missing fields, undefined references, intelligent completions

## Troubleshooting

### Backend won't start

**Error**: `ModuleNotFoundError: No module named 'tactus'`

**Solution**: Install tactus package:
```bash
cd ../../  # Go to project root
pip install -e .
```

**Error**: `Package 'tactus' requires a different Python: 3.9.6 not in '>=3.11'`

**Solution**: You need Python 3.11 or higher. Options:

1. **Use pyenv** (recommended):
```bash
# Install pyenv if not already installed
brew install pyenv

# Install Python 3.11
pyenv install 3.11.0

# Use it for this project
cd /Users/ryan.porter/Projects/Tactus
pyenv local 3.11.0

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -e .
cd tactus-ide/backend
pip install -r requirements.txt
```

2. **Use conda**:
```bash
conda create -n tactus python=3.11
conda activate tactus
pip install -e .
```

### Frontend won't start

**Error**: `npm: command not found`

**Solution**: Install Node.js from https://nodejs.org/

### LSP not connecting

**Check**: Is the backend running?
```bash
curl http://localhost:5001/health
```

Should return: `{"status": "ok", "service": "tactus-ide-backend"}`

### Validation not working

**Check**: Look at browser console (F12) for errors

**Check**: Look at backend terminal for errors

## Next Steps

- Read [tactus-ide/README.md](README.md) for full documentation
- Read [backend/README.md](backend/README.md) for backend details
- Read [frontend/README.md](frontend/README.md) for frontend details
- Try editing the example files in `../../examples/`
- Run the parser demos: `npm run demo` in frontend directory

## Architecture for Developers

### Why Hybrid?

**TypeScript parser advantages:**
- Zero network latency
- Works offline
- Reduces backend load
- Better user experience

**Python LSP advantages:**
- Semantic validation (cross-references)
- Context-aware completions
- Can integrate with runtime
- Reuses existing validation code

**Together:**
- Best of both worlds
- Fast + smart
- Offline + intelligent
- Scalable + powerful

### Technology Choices

**Monaco Editor**: Industry standard, used by VS Code, supports LSP natively

**Flask + Socket.IO**: Simple, reliable, easy to deploy

**React + Vite**: Fast development, modern tooling

**ANTLR**: Generates both parsers from single grammar

**LSP Protocol**: Standard, well-documented, tool-agnostic

## Future: Electron Packaging

The IDE is designed to be packaged as an Electron app:

```bash
# Future command
npm run electron:build
```

This will create desktop installers for:
- macOS (.dmg)
- Windows (.exe)
- Linux (.AppImage)

The architecture already supports this - no code changes needed.


