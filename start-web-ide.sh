#!/bin/bash
# Start Tactus Web IDE

set -e  # Exit on error

cd "$(dirname "$0")"

echo "========================================"
echo "Starting Tactus Web IDE"
echo "========================================"
echo ""

# Check if we're in the examples directory, if not cd there
if [ ! -d "examples" ]; then
    echo "Error: examples directory not found!"
    echo "Please run this script from the Tactus project root"
    exit 1
fi

cd examples

echo "Starting IDE from examples folder..."
echo ""
echo "The IDE will open at: http://localhost:5001"
echo "(Note: Port may be different if 5001 is in use)"
echo ""
echo "Press Ctrl+C to stop"
echo ""

tactus ide --no-browser
