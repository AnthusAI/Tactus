#!/bin/bash
#
# Entrypoint script for Tactus sandbox container.
#
# This script:
# 1. Starts any configured MCP servers from /mcp-servers
# 2. Runs the Tactus sandbox entrypoint to execute the procedure
# 3. Cleans up MCP server processes on exit
#

set -e

# Cleanup function to kill MCP servers on exit
cleanup() {
    if [ -n "$MCP_PIDS" ]; then
        echo "[sandbox] Stopping MCP servers..." >&2
        for pid in $MCP_PIDS; do
            kill "$pid" 2>/dev/null || true
        done
    fi
}
trap cleanup EXIT

MCP_PIDS=""

# Start MCP servers if directory is mounted and contains servers
if [ -d "/mcp-servers" ] && [ "$(ls -A /mcp-servers 2>/dev/null)" ]; then
    echo "[sandbox] Found MCP servers directory" >&2

    for server_dir in /mcp-servers/*/; do
        if [ ! -d "$server_dir" ]; then
            continue
        fi

        server_name=$(basename "$server_dir")
        echo "[sandbox] Starting MCP server: $server_name" >&2

        # Check for Python server
        if [ -f "${server_dir}server.py" ]; then
            # Check for virtualenv
            if [ -d "${server_dir}.venv" ]; then
                source "${server_dir}.venv/bin/activate"
                python "${server_dir}server.py" &
                deactivate
            else
                python "${server_dir}server.py" &
            fi
            MCP_PIDS="$MCP_PIDS $!"

        # Check for Node.js server
        elif [ -f "${server_dir}server.js" ]; then
            node "${server_dir}server.js" &
            MCP_PIDS="$MCP_PIDS $!"

        elif [ -f "${server_dir}index.js" ]; then
            node "${server_dir}index.js" &
            MCP_PIDS="$MCP_PIDS $!"
        fi
    done

    # Give MCP servers a moment to start
    if [ -n "$MCP_PIDS" ]; then
        sleep 1
    fi
fi

# Run the Tactus sandbox entrypoint with unbuffered I/O (-u flag)
# This ensures stdin/stdout/stderr are not buffered, enabling real-time streaming
exec python -u -m tactus.sandbox.entrypoint "$@"
