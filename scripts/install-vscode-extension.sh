#!/bin/bash
# Install Tactus VSCode extension for local development

set -e

echo "================================"
echo "Tactus VSCode Extension Installer"
echo "================================"
echo ""

# Check if we're in the right directory
if [ ! -d "tactus-vscode" ] || [ ! -d "tactus-lsp-server" ]; then
    echo "Error: Please run this script from the Tactus project root directory"
    exit 1
fi

# Check prerequisites
echo "Checking prerequisites..."
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 not found. Please install Python 3.9+"
    exit 1
fi

if ! command -v node &> /dev/null; then
    echo "Error: Node.js not found. Please install Node.js 18+"
    echo "Download from: https://nodejs.org/"
    exit 1
fi

if ! command -v npm &> /dev/null; then
    echo "Error: npm not found. Please install Node.js (includes npm)"
    exit 1
fi

echo "✓ Prerequisites OK"
echo ""

# Step 1: Install Tactus core
echo "[1/4] Installing Tactus core package..."
pip install -e .
echo "✓ Tactus core installed"
echo ""

# Step 2: Install LSP server
echo "[2/4] Installing Tactus LSP server..."
cd tactus-lsp-server
pip install -e .
cd ..
echo "✓ LSP server installed"
echo ""

# Step 3: Compile VSCode extension
echo "[3/4] Compiling VSCode extension..."
cd tactus-vscode
npm run compile
echo "✓ Extension compiled"
echo ""

# Step 4: Package and install
echo "[4/4] Packaging and installing extension..."
npm run package

# Find the .vsix file
VSIX_FILE=$(ls -t *.vsix 2>/dev/null | head -1)

if [ -z "$VSIX_FILE" ]; then
    echo "Error: Could not find .vsix file"
    exit 1
fi

echo "Installing $VSIX_FILE..."

# Try to find VSCode command
if command -v code &> /dev/null; then
    code --install-extension "$VSIX_FILE" --force
    cd ..
    echo "✓ Extension installed"
elif command -v code-insiders &> /dev/null; then
    code-insiders --install-extension "$VSIX_FILE" --force
    cd ..
    echo "✓ Extension installed (VSCode Insiders)"
else
    cd ..
    echo "⚠ 'code' command not found in PATH"
    echo ""
    echo "To install manually:"
    echo "1. Open VSCode"
    echo "2. Go to Extensions (Cmd+Shift+X or Ctrl+Shift+X)"
    echo "3. Click '...' menu → Install from VSIX"
    echo "4. Select: tactus-vscode/$VSIX_FILE"
    echo ""
    echo "Or add 'code' to PATH and run:"
    echo "  code --install-extension tactus-vscode/$VSIX_FILE"
fi

echo ""

echo "================================"
echo "Installation Complete!"
echo "================================"
echo ""
echo "Next steps:"
echo "1. Open VSCode"
echo "2. Open a .tac file"
echo "3. Check Output > Tactus Language Server for logs"
echo ""
echo "To test in development mode:"
echo "1. Open tactus-vscode/ folder in VSCode"
echo "2. Press F5 to launch Extension Development Host"
echo ""
