# Control Loop Architecture - Phase 1 Complete

## Overview

Phase 1 of the omnichannel control loop architecture is complete. This document summarizes what was implemented and how to test it.

**Status as of 2026-01-16**: Phase 1 complete but **not yet integrated** into runtime. The system currently uses the old `CLIHITLHandler` (blocking, single-channel). See [CONTROL_LOOP_INTEGRATION.md](CONTROL_LOOP_INTEGRATION.md) for Phase 2 integration tasks.

## What Was Implemented

### 1. Core Protocol ([tactus/protocols/control.py](../tactus/protocols/control.py))

- **`ControlChannel`** - Protocol for control channels (replaces old NotificationChannel)
- **`ControlRequest`** - Rich request model with:
  - Namespace for routing/authorization
  - Full conversation history
  - Prior control interactions
  - Procedure context (name, subject, elapsed time)
  - Input summary
- **`ControlResponse`** - Response from controllers (human or model)
- **`ControlRequestType`** - Enum for request types (approval, input, review, escalation)
- **`ChannelCapabilities`** - Describes what each channel supports
- **`ControlLoopConfig`** - Configuration model

### 2. Base Classes

#### InProcessChannel ([tactus/adapters/channels/base.py](../tactus/adapters/channels/base.py))

Abstract base class for channels that run in-process with asyncio:
- Response queue pattern for bridging sync/async boundaries
- Thread-safe `push_response()` methods
- Default implementations for `initialize()`, `receive()`, `cancel()`, `shutdown()`

#### HostControlChannel ([tactus/adapters/channels/host.py](../tactus/adapters/channels/host.py))

Base class for any app embedding Tactus to become a control channel:
- Background thread pattern for interruptible input
- Can be cancelled if another channel responds first
- Abstract methods for display, input collection, and cancellation messages

### 3. CLI Implementation ([tactus/adapters/channels/cli.py](../tactus/adapters/channels/cli.py))

Full CLI control channel implementation:
- Rich-formatted prompts with colors and panels
- Displays full context: procedure name, subject, elapsed time, input summary, prior interactions
- Handles all request types: approval, input, review, escalation
- Options with numbered selection
- Interruptible via background thread

### 4. Control Loop Handler ([tactus/adapters/control_loop.py](../tactus/adapters/control_loop.py))

Orchestrates multiple channels with "all channels race, first response wins" pattern:
- Sends to ALL enabled channels simultaneously
- Waits for first response from ANY channel
- Cancels other channels when one responds
- No special priority for any channel type
- Supports both synchronous (CLI) and async (remote) channels
- Integrates with storage backend for exit-and-resume pattern

### 5. Configuration

- Added control loop environment variables to [config_manager.py](../tactus/core/config_manager.py):
  - `TACTUS_CONTROL_ENABLED`
  - `TACTUS_CONTROL_CLI_ENABLED`
  - `TACTUS_CLOUD_API_URL`
  - `TACTUS_CLOUD_TOKEN`
  - `TACTUS_CLOUD_WORKSPACE_ID`

- Channel loader with auto-detection ([tactus/adapters/channels/__init__.py](../tactus/adapters/channels/__init__.py)):
  - CLI channel auto-enabled if stdin is a tty
  - Configurable via YAML or environment variables

### 6. Backward Compatibility

- Restored [cli_hitl.py](../tactus/adapters/cli_hitl.py) for existing runtime
- Old `CLIHITLHandler` still works with `TactusRuntime`
- New and old systems coexist during transition

## Architecture Highlights

### All Channels Race

```
ControlLoopHandler
    │
    ├─ Send to ALL enabled channels simultaneously
    │   ├─ Host App (CLI, IDE server, custom app)
    │   ├─ Remote channels (Tactus Cloud, Slack, etc.)
    │
    ├─ Wait for first response from ANY channel
    │
    └─ Cancel other channels: "Responded via {winning_channel}"
```

### Namespace-Based Routing (PubSub)

Control requests include a `namespace` field for routing:

```
namespace: "operations/incidents/level3-or-level4"

Subscribers:
├─ Level 0 Dashboard (observe) - sees traffic, cannot respond
├─ Level 1 Dashboard (observe) - sees traffic, cannot respond
├─ Level 3 Operator App (respond) - can see AND respond
├─ Level 4 Operator App (respond) - can see AND respond
└─ Audit System (observe) - logs everything, never responds
```

**Subscriber modes:**
- `observe` - Read-only (dashboards, monitoring, audit)
- `respond` - Can provide input (authorized controllers)

### Host App Integration

Any app embedding Tactus can become a control channel:
- CLI - Terminal interface (implemented)
- IDE - VSCode extension (Phase 2)
- Jupyter - Notebook interface (future)
- Custom apps - Web servers, desktop apps, etc.

The host app is inherently connected since it's running the runtime.

## Example Usage

### Simple HITL Example

```lua
-- examples/90-hitl-simple.tac
function main()
    -- Approval request
    local approved = Human.approve({
        message = "Would you like to continue?"
    })

    -- Input request
    local name = Human.input({
        message = "What is your name?",
        placeholder = "Enter your name..."
    })

    -- Input with options
    local color = Human.input({
        message = "What is your favorite color?",
        options = {
            {label = "Red", value = "red"},
            {label = "Blue", value = "blue"},
            {label = "Green", value = "green"}
        }
    })

    -- Review request
    local review = Human.review({
        message = "Please review this document",
        artifact = generated_text,
        artifact_type = "document"
    })

    return {
        completed = true,
        name = name,
        color = color,
        review = review
    }
end
```

### What You'll See

When running with the CLI channel:

```
╭─────────────────────────────────────────╮
│           APPROVAL                      │
│  Would you like to continue?            │
╰─────────────────────────────────────────╯
Approve? (Y/n):
```

With rich context display:

```
Customer Intake: John Doe
Started 2 minutes ago

╭─────────── Input Data ───────────╮
│ email:    john@example.com        │
│ priority: high                    │
╰───────────────────────────────────╯

Previous decisions:
  • ops_team: approved initial triage
  • support_lead: escalated to level 3

╭─────────────────────────────────────────╮
│           APPROVAL                      │
│  Escalate to engineering team?          │
╰─────────────────────────────────────────╯
Approve? (Y/n):
```

## Testing

### Run HITL Example

```bash
# With proper Python 3.11+ environment
tactus examples/90-hitl-simple.tac

# Or via Python module
python -m tactus.cli.app examples/90-hitl-simple.tac
```

### Configure Channels

Via YAML (`.tactus/config.yml`):

```yaml
control:
  enabled: true
  channels:
    cli:
      enabled: auto  # Auto-detect tty

    # Future channels
    ide:
      enabled: true

    tactus_cloud:
      enabled: true
      api_url: wss://control.tactus.cloud
      token: ${TACTUS_CLOUD_TOKEN}
      workspace_id: ${TACTUS_WORKSPACE_ID}
```

Via environment variables:

```bash
export TACTUS_CONTROL_ENABLED=true
export TACTUS_CONTROL_CLI_ENABLED=true
export TACTUS_CLOUD_TOKEN=your_token
export TACTUS_CLOUD_WORKSPACE_ID=your_workspace
```

## What's Next (Phase 2)

### IDE/SSE Channel

1. **SSEControlChannel** - Integrate with existing Flask SSE infrastructure
2. **Flask endpoints** - Add control request events and response handling
3. **VSCode extension UI** - Display control panel with full context
4. **End-to-end testing** - Verify procedure pauses, IDE displays, response resumes

This will be the first remote channel that proves the racing architecture works.

### Runtime Integration

Currently, the new control loop architecture is implemented but not yet integrated into `TactusRuntime`. Next steps:

1. Add `control_handler` parameter to `TactusRuntime` (alongside existing `hitl_handler`)
2. Update Lua DSL stubs to support both old and new APIs
3. Migrate procedures incrementally
4. Eventually deprecate old HITL system

## Files Created/Modified

### New Files

- `tactus/protocols/control.py` - Control loop protocol and models
- `tactus/adapters/channels/base.py` - InProcessChannel base class
- `tactus/adapters/channels/host.py` - Host app channel base class
- `tactus/adapters/channels/cli.py` - CLI control channel
- `tactus/adapters/control_loop.py` - Control loop handler
- `tactus/adapters/channels/__init__.py` - Channel loader
- `examples/90-hitl-simple.tac` - Simple HITL example
- `examples/91-control-loop-demo.tac` - Future API demo

### Modified Files

- `tactus/adapters/__init__.py` - Export both old and new systems
- `tactus/protocols/__init__.py` - Export control types
- `tactus/core/config_manager.py` - Add control loop env vars
- `tactus/adapters/cli_hitl.py` - Restored for backward compatibility

### Deleted Files

- Old `tactus/adapters/cli_hitl.py` - Replaced with new implementation
- Old `tactus/adapters/multichannel_hitl.py` - Replaced with control_loop.py
- Old `tactus/adapters/hitl_response_handler.py` - Not needed for Phase 1

## Summary

Phase 1 establishes the foundation for omnichannel control loop:

✅ **Architecture** - All channels race, first response wins
✅ **Protocol** - Rich context with namespace-based routing
✅ **CLI Channel** - Fully functional, interruptible
✅ **Configuration** - Environment variables and YAML
✅ **Backward Compatible** - Old HITL system still works

⏳ **Next** - IDE/SSE channel (Phase 2)
⏳ **Future** - Tactus Cloud WebSocket API (Phase 5)

The control loop architecture is ready to be extended with additional channels!
