#!/bin/bash
# Check prerequisites for building Tactus VSCode extension

echo "================================"
echo "Checking Prerequisites"
echo "================================"
echo ""

MISSING=0

# Check Python
echo -n "Python 3.9+: "
if command -v python3 &> /dev/null; then
    VERSION=$(python3 --version 2>&1 | grep -oE '[0-9]+\.[0-9]+' | head -1)
    echo "✓ Found (version $VERSION)"
else
    echo "✗ Not found"
    MISSING=1
fi

# Check Node.js
echo -n "Node.js 18+: "
if command -v node &> /dev/null; then
    VERSION=$(node --version 2>&1)
    echo "✓ Found ($VERSION)"
else
    echo "✗ Not found"
    echo "  Install: https://nodejs.org/"
    MISSING=1
fi

# Check npm
echo -n "npm:         "
if command -v npm &> /dev/null; then
    VERSION=$(npm --version 2>&1)
    echo "✓ Found (version $VERSION)"
else
    echo "✗ Not found"
    echo "  Install with Node.js: https://nodejs.org/"
    MISSING=1
fi

# Check VSCode
echo -n "VSCode:      "
if command -v code &> /dev/null; then
    VERSION=$(code --version 2>&1 | head -1)
    echo "✓ Found (version $VERSION)"
else
    echo "⚠ Command 'code' not found (but VSCode might be installed)"
    echo "  If VSCode is installed, add 'code' to PATH"
fi

echo ""
echo "================================"

if [ $MISSING -eq 0 ]; then
    echo "✓ All prerequisites met!"
    echo ""
    echo "Ready to build extension:"
    echo "  ./scripts/install-vscode-extension.sh"
else
    echo "✗ Missing prerequisites"
    echo ""
    echo "Please install missing components:"
    echo "- Python 3.9+: https://python.org/"
    echo "- Node.js 18+: https://nodejs.org/"
    echo "- VSCode: https://code.visualstudio.com/"
    exit 1
fi

echo "================================"
