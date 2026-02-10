# Tactus VSCode Extension - Quick Start

Get the Tactus VSCode extension up and running in 5 minutes!

## TL;DR

```bash
# 1. Check prerequisites
./scripts/check-prerequisites.sh

# 2. Install everything
./scripts/install-vscode-extension.sh

# 3. Open a .tac file in VSCode
code examples/01-basics-hello-world.tac
```

Done! 🎉

## What You Get

### Basic Features (Always Available)
- ✅ **Syntax Highlighting** - Color-coded Tactus DSL keywords
- ✅ **Smart Editing** - Auto-closing brackets, comment toggling
- ✅ **Code Folding** - Collapse/expand blocks

### Enhanced Features (With LSP Server)
- ✅ **Real-time Validation** - Red squiggles for errors
- ✅ **Code Completion** - Type `Ag` → suggests `Agent`
- ✅ **Hover Info** - Hover over agent → see configuration
- ✅ **Semantic Highlighting** - Agents, tools, properties in unique colors
- ✅ **Signature Help** - Parameter hints as you type

## Installation

### Prerequisites

- Python 3.9+
- Node.js 18+
- VSCode 1.75+

Check if you have them:
```bash
./scripts/check-prerequisites.sh
```

### One-Command Install

```bash
./scripts/install-vscode-extension.sh
```

This installs:
1. Tactus core Python package
2. tactus-lsp-server (provides LSP features)
3. VSCode extension (packaged as .vsix)

### Verify It Works

```bash
# Test LSP server
./scripts/test-lsp-server.sh

# Open a test file
code examples/01-basics-hello-world.tac
```

In VSCode:
1. Check syntax highlighting appears
2. Go to Output panel (View > Output)
3. Select "Tactus Language Server" from dropdown
4. Should see: "Starting Tactus LSP Server..."

## Usage

### Basic Editing

**Comment/Uncomment:**
- Mac: `Cmd + /`
- Windows/Linux: `Ctrl + /`

**Auto-complete:**
- Type: `Ag` then `Ctrl + Space`
- Select: `Agent` from suggestions

**Hover Documentation:**
- Hover cursor over any agent/tool name
- See configuration details

### Testing Features

Open `examples/04-basics-simple-agent.tac` and try:

1. **Validation:**
   - Change line 5: `greeter = Agentt {` (typo)
   - See red squiggle under `Agentt`
   - Hover to see error message

2. **Completion:**
   - Type: `field.`
   - See: `field.string`, `field.number`, etc.

3. **Hover:**
   - Hover over: `greeter` on line 28
   - See agent configuration

4. **Semantic Colors:**
   - Notice `greeter` has unique color (agent)
   - Notice `done` has different color (tool)
   - Notice `provider`, `model` have property color

## Troubleshooting

### "Python not found"
```bash
# Install Python 3.9+
# macOS: brew install python@3.11
# Linux: sudo apt install python3.11
# Windows: https://python.org/downloads/
```

### "LSP Server not found"
```bash
cd tactus-lsp-server
pip install -e .
```

### "Syntax highlighting works but no validation"

LSP server isn't running. Check:
1. Output > Tactus Language Server for errors
2. Run: `./scripts/test-lsp-server.sh`
3. Reinstall: `pip install -e tactus-lsp-server/ --force-reinstall`

### "Extension not loading"

```bash
# Reinstall extension
cd tactus-vscode
npm run package
code --install-extension tactus-0.1.0.vsix --force
```

## Development

### Test in Development Mode

```bash
cd tactus-vscode
code .
```

Press **F5** → launches Extension Development Host

### Make Changes

**Edit syntax highlighting:**
- File: `tactus-vscode/syntaxes/tactus.tmLanguage.json`
- Reload: `Cmd+R` in Extension Host

**Edit LSP features:**
- File: `tactus-lsp-server/tactus_lsp_server/handler.py`
- Restart: `Ctrl+R` in Extension Host

See [CONTRIBUTING.md](CONTRIBUTING.md) for full development guide.

## Next Steps

1. **Try examples:** Open files in `examples/` directory
2. **Write Tactus code:** Create your own `.tac` files
3. **Explore features:** Hover, completions, validation
4. **Report issues:** https://github.com/AnthusAI/Tactus/issues

## Resources

- Full install guide: [INSTALL.md](INSTALL.md)
- Contributing: [CONTRIBUTING.md](CONTRIBUTING.md)
- Main docs: [README.md](README.md)
- Tactus docs: https://github.com/AnthusAI/Tactus

---

**Enjoy coding in Tactus! 🚀**
