#!/bin/bash
# Rebuild and test script for Tactus Desktop App

set -e  # Exit on error

echo "========================================"
echo "Rebuilding Tactus Desktop App"
echo "========================================"

cd "$(dirname "$0")"

echo ""
echo "Step 1/3: Building frontend..."
npm run build:frontend

echo ""
echo "Step 2/3: Building backend with PyInstaller..."
npm run build:backend

echo ""
echo "Step 3/3: Building TypeScript and packaging..."
npm run build
npx electron-builder --mac --dir

echo ""
echo "========================================"
echo "Build complete!"
echo "========================================"
echo ""
echo "To launch the app:"
echo "  open \"dist-electron/mac-arm64/Tactus IDE.app\""
echo ""
echo "To view logs:"
echo "  tail -f \"$HOME/Library/Logs/Tactus IDE/main.log\""
echo ""
