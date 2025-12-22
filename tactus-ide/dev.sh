#!/bin/bash
# Development mode: backend auto-restart + frontend rebuild-on-change (no Vite dev server)

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}Starting Tactus IDE in development mode...${NC}"
echo -e "${YELLOW}Backend will auto-reload on Python changes${NC}"
echo -e "${YELLOW}Frontend will rebuild on TS/React changes (refresh browser)${NC}"
echo ""

# Find tactus-ide directory (where this script lives) and project root
TACTUS_IDE_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$TACTUS_IDE_DIR/.." && pwd)"

# Function to find an available port
find_available_port() {
    local start_port=$1
    local max_attempts=${2:-10}
    local port=$start_port
    
    for ((i=0; i<max_attempts; i++)); do
        if ! lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
            echo $port
            return 0
        fi
        port=$((port + 1))
    done
    
    echo -e "${RED}Error: Could not find available port starting from $start_port${NC}" >&2
    return 1
}

# Find available ports with auto-increment
BACKEND_START_PORT="${TACTUS_IDE_BACKEND_PORT:-5001}"
FRONTEND_START_PORT="${TACTUS_IDE_FRONTEND_PORT:-3000}"

echo -e "${YELLOW}Finding available ports...${NC}"
BACKEND_PORT=$(find_available_port $BACKEND_START_PORT)
if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to find available backend port${NC}"
    exit 1
fi

FRONTEND_PORT=$(find_available_port $FRONTEND_START_PORT)
if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to find available frontend port${NC}"
    exit 1
fi

if [ "$BACKEND_PORT" != "$BACKEND_START_PORT" ]; then
    echo -e "${YELLOW}Backend port $BACKEND_START_PORT in use, using port $BACKEND_PORT${NC}"
fi

if [ "$FRONTEND_PORT" != "$FRONTEND_START_PORT" ]; then
    echo -e "${YELLOW}Frontend port $FRONTEND_START_PORT in use, using port $FRONTEND_PORT${NC}"
fi

# Check if watchdog is installed (for Python auto-reload)
if ! python -c "import watchdog" 2>/dev/null; then
    echo -e "${YELLOW}Installing watchdog for Python auto-reload...${NC}"
    pip install 'watchdog[watchmedo]' -q
fi

# Cleanup function
cleanup() {
    echo -e "\n${YELLOW}Shutting down...${NC}"
    kill $(jobs -p) 2>/dev/null || true
    exit 0
}

trap cleanup SIGINT SIGTERM EXIT

# Suppress Python warnings for cleaner output
export PYTHONWARNINGS="ignore::DeprecationWarning,ignore::RuntimeWarning,ignore::UserWarning"

# Start backend with auto-reload using watchmedo
echo -e "${GREEN}Starting backend with auto-reload on port ${BACKEND_PORT}...${NC}"
cd "$PROJECT_ROOT"

# Set initial workspace to examples folder
INITIAL_WORKSPACE="$PROJECT_ROOT/examples"
if [ -d "$INITIAL_WORKSPACE" ]; then
    echo -e "${BLUE}Setting initial workspace to: $INITIAL_WORKSPACE${NC}"
else
    echo -e "${YELLOW}Warning: examples folder not found, using project root${NC}"
    INITIAL_WORKSPACE="$PROJECT_ROOT"
fi

# Use watchmedo with better settings to avoid restart loops
# Watch both tactus/ide, tactus/testing, and tactus-ide/backend for changes
watchmedo auto-restart \
    --directory="$PROJECT_ROOT/tactus/ide" \
    --directory="$PROJECT_ROOT/tactus/testing" \
    --directory="$PROJECT_ROOT/tactus-ide/backend" \
    --pattern="*.py" \
    --recursive \
    --ignore-patterns="*/__pycache__/*;*.pyc;*/.pytest_cache/*;*/.*" \
    --ignore-directories \
    --debounce-interval=2 \
    -- env TACTUS_IDE_PORT="$BACKEND_PORT" TACTUS_IDE_WORKSPACE="$INITIAL_WORKSPACE" python -W ignore -m tactus.ide.server &

BACKEND_PID=$!

# Give backend time to start
echo -e "${YELLOW}Waiting for backend to start...${NC}"
for i in 1 2 3 4 5 6 7 8 9 10; do
  if curl -s "http://127.0.0.1:${BACKEND_PORT}/health" > /dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

# Check if backend is running
if curl -s "http://127.0.0.1:${BACKEND_PORT}/health" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Backend started successfully${NC}"
else
    echo -e "${RED}⚠ Backend may not have started properly${NC}"
    echo -e "${YELLOW}Check output above for errors${NC}"
fi

# Start frontend build watcher (writes into dist/)
echo -e "${GREEN}Starting frontend rebuild watcher...${NC}"
cd "$TACTUS_IDE_DIR/frontend"

# Ensure backend URL is embedded into the frontend bundle
export VITE_BACKEND_URL="http://127.0.0.1:${BACKEND_PORT}"
echo -e "${BLUE}Setting VITE_BACKEND_URL=${VITE_BACKEND_URL}${NC}"
npm run build -- --watch &

FRONTEND_BUILD_PID=$!

# Serve dist/ (simple static server)
echo -e "${GREEN}Serving frontend from dist on port ${FRONTEND_PORT}...${NC}"
python -m http.server "$FRONTEND_PORT" --directory "$TACTUS_IDE_DIR/frontend/dist" >/dev/null 2>&1 &

FRONTEND_SERVER_PID=$!

# Wait for both processes
echo ""
echo -e "${GREEN}✓ Development servers running!${NC}"
echo -e "  Frontend: ${BLUE}http://localhost:${FRONTEND_PORT}${NC} (rebuild-on-change; refresh browser)"
echo -e "  Backend:  ${BLUE}http://127.0.0.1:${BACKEND_PORT}${NC} (auto-restart enabled)"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop all servers${NC}"
echo ""

# Wait for any process to exit
wait








