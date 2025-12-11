# Tactus IDE CLI Command

## Usage

```bash
# Start IDE (auto-detects available ports)
tactus ide

# Start on specific backend port
tactus ide --port 5001

# Start without opening browser
tactus ide --no-browser

# Start with verbose logging
tactus ide --verbose
```

## What It Does

1. **Finds Available Ports**
   - Backend: Tries port 5001, if busy uses any available port
   - Frontend: Tries port 3000, if busy uses any available port

2. **Builds Frontend** (if needed)
   - Checks if `tactus-ide/frontend/dist/` exists
   - If not, runs `npm run build` with backend URL in environment

3. **Starts Backend Server**
   - Runs Flask app in background thread
   - Provides LSP endpoints for validation and completions

4. **Starts Frontend Server**
   - Serves built frontend using Python's SimpleHTTPServer
   - Runs in background thread

5. **Opens Browser** (unless --no-browser)
   - Opens default browser to frontend URL

6. **Runs Until Interrupted**
   - Press Ctrl+C to stop both servers

## Implementation Details

### Port Detection

```python
def find_available_port(preferred_port=None):
    """Find an available port, preferring the specified port if available."""
    if preferred_port:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind(('127.0.0.1', preferred_port))
            sock.close()
            return preferred_port
        except OSError:
            pass
    
    # Let OS assign an available port
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(('127.0.0.1', 0))
    assigned_port = sock.getsockname()[1]
    sock.close()
    return assigned_port
```

### Backend URL Passing

The backend URL is passed to the frontend via environment variable:
- `VITE_BACKEND_URL=http://localhost:{port}` is set before running `npm run build`
- Frontend reads it: `import.meta.env.VITE_BACKEND_URL`
- Falls back to `http://localhost:5001` if not set

### Module Structure

```
tactus/
├── ide/
│   ├── __init__.py     - Module exports
│   └── server.py       - Flask app with LSP endpoints
│
└── cli/
    └── app.py          - Added ide() command
```

## Example Output

```
╭──────────────────────────────────────────────────────────────────────────────╮
│ Starting Tactus IDE                                                          │
╰──────────────────────────────────────────────────────────────────────────────╯
Backend port: 5001
Frontend port: 3000
✓ Backend server started on http://127.0.0.1:5001
✓ Frontend server started on http://localhost:3000

Opening browser to http://localhost:3000

Press Ctrl+C to stop the IDE
```

## Port Conflict Handling

If ports are in use:

```
Backend port: 5002                          <- Auto-incremented
Note: Port 3000 in use, using 3001          <- Frontend fallback
Frontend port: 3001
✓ Backend server started on http://127.0.0.1:5002
✓ Frontend server started on http://localhost:3001
```

## Advantages

1. **Self-Contained**: Single command starts everything
2. **Smart Port Detection**: Automatically finds available ports
3. **No Manual Steps**: Builds frontend if needed
4. **Clean Shutdown**: Ctrl+C stops both servers
5. **Works Offline**: Once built, frontend cached

## Testing

```bash
# Clean test
pkill -f tactus; tactus ide --no-browser

# Test port conflict
tactus ide --port 5001 &  # First instance
tactus ide                # Second instance finds different ports

# Test with specific port
tactus ide --port 8080

# Test verbose mode
tactus ide --verbose
```

## Implementation Status

- [x] Port detection for backend
- [x] Port detection for frontend  
- [x] Frontend build on first run
- [x] Environment variable passing
- [x] Background server threads
- [x] Browser auto-open
- [x] Graceful shutdown
- [x] Verbose logging option
- [x] Clean console output

