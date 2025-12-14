# IDE Server Behavior Specification

## Overview
The Tactus IDE server implements automatic port detection and conflict resolution to enable multiple instances to run simultaneously without manual configuration.

## Feature File
`features/19_ide_server.feature`

## Key Behaviors

### 1. Port Auto-Detection
**Default Behavior:**
- Backend prefers port 5001
- Frontend prefers port 3000
- If preferred port is available, use it
- If preferred port is occupied, OS assigns next available port

**Implementation:**
```python
def find_available_port(preferred_port=None):
    if preferred_port:
        try:
            sock.bind(("127.0.0.1", preferred_port))
            return preferred_port
        except OSError:
            pass
    
    # Let OS assign available port
    sock.bind(("127.0.0.1", 0))
    return sock.getsockname()[1]
```

### 2. Multiple Instance Support
**Scenario:** Two IDE instances running simultaneously
- Instance 1: Backend 5001, Frontend 3000
- Instance 2: Backend auto-assigned, Frontend auto-assigned
- Both function independently
- No manual configuration required

### 3. Electron Integration
**Port Detection Flow:**
1. Electron spawns `tactus ide --no-browser`
2. Backend starts and prints: `Backend port: 5001`
3. Frontend starts and prints: `Frontend port: 3000`
4. Electron parses stdout to detect ports
5. Electron window loads `http://localhost:{detected_port}`

### 4. Graceful Degradation
**Port Conflict Handling:**
- User sees: `Note: Port 3000 in use, using 3001`
- IDE continues to function normally
- No error, no crash, no manual intervention

### 5. Health Monitoring
**Endpoint:** `GET /health`
**Response:**
```json
{
  "status": "ok",
  "service": "tactus-ide-backend"
}
```

## Test Coverage

### Positive Tests
- ✅ Start on default ports (5001, 3000)
- ✅ Start when backend port occupied
- ✅ Start when frontend port occupied
- ✅ Start when both ports occupied
- ✅ Run multiple instances
- ✅ Custom port specification
- ✅ Electron port detection

### Negative Tests
- ✅ Graceful shutdown (Ctrl+C)
- ✅ Timeout handling (30s limit)
- ✅ Port release verification
- ✅ Health check availability

### Edge Cases
- ✅ Race condition prevention (backend before frontend)
- ✅ Custom port also occupied (fallback)
- ✅ No browser mode (--no-browser)

## Running the Tests

```bash
# Run all IDE server tests
behave features/19_ide_server.feature

# Run specific scenario
behave features/19_ide_server.feature -n "Starting IDE on default ports"

# Run with verbose output
behave features/19_ide_server.feature -v
```

## Implementation Files

### Backend
- `tactus/cli/app.py` - CLI command with port detection
- `tactus/ide/server.py` - Flask backend server

### Desktop
- `tactus-desktop/src/backend-manager.ts` - Electron backend spawning
- `tactus-desktop/src/main.ts` - Electron main process

## Design Principles

### 1. Zero Configuration
Users should never need to manually configure ports. The system finds available ports automatically.

### 2. Fail-Safe
Port conflicts are handled gracefully. The IDE continues to function even when preferred ports are unavailable.

### 3. Observable
Port assignments are clearly communicated in console output:
```
Backend port: 5001
Frontend port: 3000
✓ Backend server started on http://127.0.0.1:5001
✓ Frontend server started on http://localhost:3000
```

### 4. Composable
Multiple IDE instances can coexist. Electron and browser versions can run simultaneously.

### 5. Deterministic
Port selection follows a predictable algorithm:
1. Try preferred port
2. If occupied, let OS assign
3. Report selected port
4. Continue startup

## Future Enhancements

### Port Range Configuration
```bash
# Specify port range
tactus ide --port-range 5001-5010
```

### Port Persistence
```yaml
# .tactus/config.yml
ide:
  backend_port: 5001
  frontend_port: 3000
  auto_detect: true
```

### Port Discovery
```bash
# List running IDE instances
tactus ide list

# Output:
# Instance 1: Backend 5001, Frontend 3000 (Browser)
# Instance 2: Backend 5002, Frontend 3001 (Electron)
```

## Related Documentation
- [IDE Overhaul Summary](../../tactus-ide/IDE_OVERHAUL_SUMMARY.md)
- [Quick Start Guide](../../tactus-ide/QUICK_START.md)
- [Specification](../../SPECIFICATION.md)






