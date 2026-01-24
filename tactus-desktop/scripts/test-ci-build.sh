#!/bin/bash
# Test script to simulate CI build environment locally
# This helps catch missing dependencies before pushing to GitHub

set -e

echo "========================================="
echo "Testing CI Build Environment Locally"
echo "========================================="
echo ""
echo "This script simulates the CI build by creating a fresh"
echo "Python virtual environment and building the app."
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

cd "$(dirname "$0")/.."

# Create a temporary virtual environment
VENV_DIR=$(mktemp -d -t tactus-ci-test-XXXXXX)
echo -e "${YELLOW}Creating fresh virtual environment at: ${VENV_DIR}${NC}"
python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

# Trap to cleanup on exit
cleanup() {
    echo ""
    echo -e "${YELLOW}Cleaning up virtual environment...${NC}"
    deactivate 2>/dev/null || true
    rm -rf "$VENV_DIR"
}
trap cleanup EXIT

echo ""
echo -e "${YELLOW}Installing dependencies (like CI does)...${NC}"
cd ..
python -m pip install --upgrade pip --quiet
pip install pyinstaller --quiet
pip install -e . --quiet

echo ""
echo -e "${YELLOW}Building backend with PyInstaller...${NC}"
cd tactus-desktop
npm run build:backend

# Check if Flask was bundled
echo ""
echo -e "${YELLOW}Checking if Flask was bundled...${NC}"
if [ -d "backend/dist/tactus/_internal" ]; then
    if find backend/dist/tactus/_internal -name "*flask*" -o -name "*Flask*" | grep -q .; then
        echo -e "${GREEN}✓ Flask found in bundle${NC}"
    else
        echo -e "${RED}✗ Flask NOT found in bundle - this will fail in CI!${NC}"
        exit 1
    fi
fi

# Check if tactus.ide.server is importable
echo ""
echo -e "${YELLOW}Checking if tactus.ide modules are importable...${NC}"
python -c "from tactus.ide import server; from tactus.ide import config_server" 2>/dev/null && \
    echo -e "${GREEN}✓ tactus.ide modules can be imported${NC}" || \
    { echo -e "${RED}✗ tactus.ide modules cannot be imported - check dependencies!${NC}"; exit 1; }

echo ""
echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}CI Build Test PASSED!${NC}"
echo -e "${GREEN}=========================================${NC}"
echo ""
echo "The build should work in GitHub Actions."
