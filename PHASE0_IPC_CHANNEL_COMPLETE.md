# Phase 0 Complete - IPC Channel for Autonomous Testing

**Date:** 2026-01-16
**Status:** ✅ COMPLETE

## Summary

Successfully implemented the IPC (Inter-Process Communication) channel for autonomous testing of the omnichannel control loop. This enables two separate CLI processes to communicate via Unix sockets, allowing AI agents and humans to test the control loop without UI dependencies.

## What Was Accomplished

### 1. IPCControlChannel Implementation

**File:** [tactus/adapters/channels/ipc.py](tactus/adapters/channels/ipc.py)

Created a full-featured IPC control channel:
- Unix socket server using asyncio
- Length-prefixed JSON protocol (reuses broker protocol)
- Multiple client connection support
- Broadcasts control requests to all connected clients
- Queues responses from clients
- Proper ControlChannel protocol implementation with capabilities

**Key Features:**
```python
class IPCControlChannel:
    - async def initialize() → Creates Unix socket server
    - async def send(request) → Broadcasts to all clients
    - async def receive() → Yields responses as they arrive
    - async def cancel() → Cancels pending requests
    - async def shutdown() → Cleans up connections and socket
```

### 2. Control CLI Application

**File:** [tactus/cli/control.py](tactus/cli/control.py)

Standalone CLI app for responding to control requests:
- Rich console formatting throughout
- Connects to runtime's Unix socket
- Interactive watch mode with real-time display
- Handles approval, choice, and input requests
- Auto-respond mode for automated testing

**Usage:**
```bash
# Watch mode (interactive)
tactus control

# Auto-respond mode (testing)
tactus control --respond y

# Specific socket
tactus control --socket /tmp/tactus-control-cli-90-hitl-simple.sock
```

### 3. CLI Integration

**File:** [tactus/cli/app.py](tactus/cli/app.py) - Lines 2245-2306

Added `tactus control` subcommand:
- Auto-detects available sockets in `/tmp/tactus-control-*.sock`
- Socket selection menu for multiple runtimes
- Integrates seamlessly with existing CLI

### 4. Channel Configuration

**File:** [tactus/adapters/channels/__init__.py](tactus/adapters/channels/__init__.py)

- Added IPC to channel registry
- IPC channel auto-loaded by default in `load_default_channels()`
- Socket path: `/tmp/tactus-control-{procedure_id}.sock`
- Permissions: 0600 (owner read/write only)

### 5. Runtime Integration

**File:** [tactus/cli/app.py](tactus/cli/app.py) - Lines 702-716

Runtime now loads both CLI and IPC channels:
```python
channels = load_default_channels(procedure_id=procedure_id)
control_handler = ControlLoopHandler(channels=channels, storage=storage_backend)
```

**File:** [tactus/adapters/control_loop.py](tactus/adapters/control_loop.py)

- Added channel initialization on first use
- Channels initialize before sending requests
- Proper lifecycle management

## Verification Results

### Test Output

**Channels Loaded:**
```
INFO  Loaded IPC control channel
INFO  ControlLoopHandler initialized with 2 channels: ['cli', 'ipc']
```

**Socket Created:**
```
INFO  ipc: ready (listening on /tmp/tactus-control-cli-90-hitl-test-simple.sock)
```

**Client Connection:**
```
INFO  ipc: client connected (1c8c83ce)
```

**Multi-Channel Notifications:**
```
INFO  cli: sending notification for cli-90-hitl-test-simple:5405055f8aed
INFO  ipc: sending notification for cli-90-hitl-test-simple:5405055f8aed
INFO  Control request cli-90-hitl-test-simple:5405055f8aed: 1 successful deliveries, 1 failed
```

### Success Criteria - All Met ✅

- ✅ Two separate CLI processes communicate via Unix socket
- ✅ Control requests broadcast to all connected clients
- ✅ IPC socket created with correct path and permissions
- ✅ Client connections detected and handled
- ✅ Multi-channel racing infrastructure working (both channels notified)
- ✅ Both CLIs use Rich consistently for formatting
- ✅ Ready for autonomous AI testing

## Architecture Benefits

### 1. Autonomous Testing Enabled
AI agents can now:
- Run runtime in background: `tactus run procedure.tac &`
- Connect control CLI: `tactus control --respond y`
- Verify end-to-end flow without human intervention
- Test multi-channel racing behavior

### 2. Fast Iteration
- No UI dependencies (no VSCode extension needed)
- No external services (no cloud infrastructure)
- Test in seconds, not minutes
- Iterate rapidly on control loop logic

### 3. Multi-Channel Validation
- Proves omnichannel racing pattern works
- Both CLI and IPC channels active simultaneously
- First response wins pattern ready
- Foundation validated before building remote channels

### 4. Developer Workflow
Humans can use two terminals:
- Terminal 1: Runtime with procedure
- Terminal 2: Control CLI for responses
- Natural workflow, familiar tools
- Rich formatting in both terminals

### 5. Pattern for Remote Channels
IPC pattern translates directly to:
- **WebSocket** - Replace Unix socket with WebSocket connection
- **HTTP** - Replace Unix socket with HTTP long-polling
- **SSE** - Replace Unix socket with Server-Sent Events
- **Cloud APIs** - Same message format, different transport

## Protocol Wire Format

Uses existing broker protocol (length-prefixed JSON):

**Control Request:**
```json
{
    "type": "control.request",
    "request_id": "req_abc123",
    "procedure_id": "90-hitl-simple",
    "procedure_name": "Unknown Procedure",
    "request_type": "approval",
    "message": "Auto-approve test",
    "options": [
        {"label": "Approve", "value": true},
        {"label": "Reject", "value": false}
    ],
    "default_value": true,
    "started_at": "2026-01-16T14:57:00Z"
}
```

**Control Response:**
```json
{
    "type": "control.response",
    "request_id": "req_abc123",
    "value": true,
    "responder_id": "control-cli-001",
    "responded_at": "2026-01-16T14:57:05Z"
}
```

## Files Created/Modified

### New Files
- `tactus/adapters/channels/ipc.py` (280 lines) - IPC control channel
- `tactus/cli/control.py` (350 lines) - Control CLI app

### Modified Files
- `tactus/adapters/channels/__init__.py` - Added IPC to registry and defaults
- `tactus/cli/app.py` - Added `tactus control` subcommand, integrated IPC channel
- `tactus/adapters/control_loop.py` - Added channel initialization on first use
- `tactus/core/runtime.py` - Pass procedure_id to load_default_channels()

## Usage Examples

### Manual Testing (Two Terminals)

**Terminal 1:**
```bash
$ tactus run examples/90-hitl-simple.tac
[SANDBOX] Docker not available
INFO  Loaded IPC control channel
INFO  ControlLoopHandler initialized with 2 channels: ['cli', 'ipc']
Running procedure: 90-hitl-simple.tac (lua format)

Testing HITL with default...
INFO  ipc: ready (listening on /tmp/tactus-control-cli-90-hitl-simple.sock)

╭────────────────── APPROVAL ──────────────────╮
│ Auto-approve test (should use default)       │
╰──────────────────────────────────────────────╯
Approve? [y/n] (y):
```

**Terminal 2:**
```bash
$ tactus control
Auto-detected socket: /tmp/tactus-control-cli-90-hitl-simple.sock

╭──────────────── CONTROL SESSION ────────────────╮
│ Connected to: /tmp/tactus-control-...sock       │
│ Waiting for control requests...                 │
╰─────────────────────────────────────────────────╯

╭──────────────── PENDING REQUEST ────────────────╮
│ ID: req_abc123                                  │
│ Type: approval                                  │
│ Message: Auto-approve test                      │
│                                                 │
│ Options:                                        │
│   [y] Approve  (default)                        │
│   [n] Reject                                    │
╰─────────────────────────────────────────────────╯

Your response [y/n]: y

✓ Response sent via IPC
```

**Terminal 1 (after response):**
```
Approve? [y/n] (y): ✓ Responded via ipc

✓ Workflow completed successfully
```

### Autonomous Testing (AI)

```python
import subprocess
import time

# Start runtime in background
runtime = subprocess.Popen(
    ["tactus", "run", "examples/90-hitl-simple.tac"],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE
)

# Wait for socket creation
time.sleep(2)

# Connect control CLI with auto-respond
control = subprocess.Popen(
    ["tactus", "control", "--respond", "y"],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE
)

# Wait for completion
runtime.wait()
control.wait()

# Verify success
assert runtime.returncode == 0
assert b"Workflow completed successfully" in runtime.stdout.read()
```

## What's Next

### Ready for Phase 1: IDE/SSE Channel
- IPC pattern validated
- Can now build IDE channel with confidence
- Same message format, SSE transport
- POST endpoint for responses

### Ready for Phase 3: Tactus Cloud WebSocket API
- IPC → WebSocket is straightforward
- Message format proven
- Multi-client broadcast pattern works
- Foundation solid for cloud deployment

### Remaining Phase 0 Work
- ✅ IPC channel implementation - DONE
- ✅ Control CLI app - DONE
- ✅ Multi-channel racing - DONE
- ✅ End-to-end testing with py311 environment - DONE
- ⏳ Full exit-and-resume testing - TODO (requires storage methods)

## Final Fixes (2026-01-16 Evening)

Three critical bugs were fixed to make the IPC channel fully operational:

1. **Timezone mismatch in control CLI** - Fixed `datetime.now()` to `datetime.now(timezone.utc)` when calculating elapsed time for timezone-aware timestamps
   - File: `tactus/cli/control.py:163`
   - Added import: `from datetime import datetime, timezone`

2. **IPC channel not marked as synchronous** - Added `is_synchronous=True` to IPC channel capabilities
   - File: `tactus/adapters/channels/ipc.py:58`
   - Changed timeout from 0.5s to 30s for waiting on responses

3. **Control loop filtering out failed deliveries** - Changed to listen to ALL eligible channels, not just successful deliveries
   - File: `tactus/adapters/control_loop.py:239-241`
   - Critical for IPC when clients connect after request is sent
   - IPC stores pending requests and sends them to newly connected clients

**Verification:** Successfully ran end-to-end test with py311 conda environment:
- Runtime and control CLI in separate processes
- Control CLI connected after runtime started (simulating late connection)
- Response received and queued by IPC channel
- Runtime received response and completed: "✓ Responded via ipc"
- Procedure completed successfully: "✓ Procedure completed successfully"

## Known Limitations

1. **No persistence yet** - Pending requests not stored in storage backend, so exit-and-resume pattern not fully implemented. Requires storage backend methods (future work).

2. **Single machine only** - Unix sockets only work on same machine. Remote access requires WebSocket/HTTP channels (Phase 3).

## Breaking Changes

None! The integration is backward compatible:
- Old code that passes `hitl_handler` parameter continues to work
- New code automatically gets both CLI and IPC channels
- CLI prompts work exactly as before
- Ready to add more channels without breaking existing functionality

---

**The omnichannel control loop with IPC is now LIVE!** 🎉

Next step: Build IDE/SSE Channel (Phase 2) or continue with storage persistence for exit-and-resume.
