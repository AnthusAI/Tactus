# Tactus VSCode Extension - Installation Guide

## Prerequisites

Before installing the extension, ensure you have:

- **Python 3.9+** (for LSP server)
- **Node.js 18+** and npm (for building the extension)
- **VSCode 1.75+**

### Installing Prerequisites

#### macOS
```bash
# Install Node.js via Homebrew
brew install node

# Or download from https://nodejs.org/
```

#### Linux
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install nodejs npm

# Fedora
sudo dnf install nodejs npm
```

#### Windows
Download and install from https://nodejs.org/

## Installation Methods

### Method 1: Quick Install (Recommended)

If you have all prerequisites installed:

```bash
cd /path/to/Tactus
./scripts/install-vscode-extension.sh
```

This script will:
1. Install Tactus core package
2. Install tactus-lsp-server
3. Compile the VSCode extension
4. Package and install it in VSCode

### Method 2: Manual Installation

#### Step 1: Install LSP Server

```bash
cd tactus-lsp-server
pip install -e .
```

Verify installation:
```bash
python3 -m tactus_lsp_server.stdio_server --version
```

#### Step 2: Build Extension

```bash
cd tactus-vscode

# Install client dependencies
cd client
npm install
cd ..

# Compile TypeScript
npm run compile
```

#### Step 3: Package Extension

```bash
# Still in tactus-vscode/
npm run package
```

This creates `tactus-0.1.0.vsix`

#### Step 4: Install in VSCode

```bash
code --install-extension tactus-0.1.0.vsix
```

Or manually in VSCode:
1. Open VSCode
2. Go to Extensions (Cmd+Shift+X / Ctrl+Shift+X)
3. Click "..." menu → "Install from VSIX..."
4. Select `tactus-0.1.0.vsix`

### Method 3: Development Mode

For active development without installing:

```bash
cd tactus-vscode
code .
```

Then press **F5** to launch Extension Development Host.

## Verifying Installation

### 1. Check LSP Server

```bash
./scripts/test-lsp-server.sh
```

Should output:
```
✓ LSP server package found
✓ Server started successfully
✓ Server responds to LSP messages
All Tests Passed!
```

### 2. Test Extension

1. Open VSCode
2. Open any `.tac` file (try `examples/01-basics-hello-world.tac`)
3. Check for:
   - ✅ Syntax highlighting appears
   - ✅ "Tactus Language Server" in Output panel
   - ✅ No errors in Output > Tactus Language Server

## Troubleshooting

### Error: "Python not found"

**Solution:**
```bash
# macOS/Linux
which python3

# Windows
where python
```

If not found, install Python 3.9+ from https://python.org/

### Error: "tactus-lsp-server not found"

**Solution:**
```bash
pip install -e tactus-lsp-server/
```

### Error: "npm: command not found"

**Solution:**
Install Node.js from https://nodejs.org/ or via package manager.

### Error: "tsc: command not found"

**Solution:**
The compile script should use `npx tsc` automatically. If it doesn't:
```bash
cd tactus-vscode/client
npm install
npx tsc -b
```

### Extension Loads But No LSP Features

**Symptoms:**
- Syntax highlighting works
- No validation, completions, or hover

**Solution:**
1. Check Output > Tactus Language Server for errors
2. Verify LSP server: `./scripts/test-lsp-server.sh`
3. Reinstall LSP server: `pip install -e tactus-lsp-server/ --force-reinstall`

### LSP Server Crashes

**Solution:**
1. Check logs: Output > Tactus Language Server
2. Run server manually to see errors:
   ```bash
   python3 -m tactus_lsp_server.stdio_server
   ```
3. Check Tactus core is installed: `pip show tactus`

## Uninstalling

### Remove Extension

```bash
code --uninstall-extension tactus.tactus
```

Or via VSCode: Extensions > Tactus > Uninstall

### Remove LSP Server

```bash
pip uninstall tactus-lsp-server
```

## Next Steps

Once installed:

1. **Open a `.tac` file** - Try any file in `examples/`
2. **Test features**:
   - Type `Ag` and press Ctrl+Space → see completions
   - Hover over agent name → see configuration
   - Introduce a typo → see red squiggle
3. **Check logs**: Output > Tactus Language Server

## Getting Help

- Check [CONTRIBUTING.md](CONTRIBUTING.md) for development setup
- Open an issue: https://github.com/AnthusAI/Tactus/issues
- Read VSCode docs: https://code.visualstudio.com/api
