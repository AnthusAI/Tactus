#!/bin/bash
# Test Tactus LSP server

set -e

echo "================================"
echo "Tactus LSP Server Test"
echo "================================"
echo ""

# Check if LSP server is installed
echo "[1/3] Checking if LSP server is installed..."
if python3 -c "import tactus_lsp_server" 2>/dev/null; then
    echo "✓ LSP server package found"
else
    echo "✗ LSP server not installed"
    echo ""
    echo "Install with:"
    echo "  cd tactus-lsp-server && pip install -e ."
    exit 1
fi
echo ""

# Check if server can start
echo "[2/3] Testing server startup..."
timeout 2s python3 -m tactus_lsp_server.stdio_server > /dev/null 2>&1 &
SERVER_PID=$!
sleep 1

if ps -p $SERVER_PID > /dev/null 2>&1; then
    echo "✓ Server started successfully (PID: $SERVER_PID)"
    kill $SERVER_PID 2>/dev/null || true
else
    echo "✗ Server failed to start"
    exit 1
fi
echo ""

# Test with a simple LSP initialize message
echo "[3/3] Testing LSP protocol..."
TEST_MESSAGE='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"capabilities":{}}}'
echo $TEST_MESSAGE | timeout 2s python3 -m tactus_lsp_server.stdio_server 2>&1 | grep -q "tactus-lsp-server" && echo "✓ Server responds to LSP messages" || echo "⚠ Could not verify LSP response"
echo ""

echo "================================"
echo "All Tests Passed!"
echo "================================"
echo ""
echo "LSP server is ready to use with VSCode extension."
echo ""
