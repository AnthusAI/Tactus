# Control Loop Integration - Phase 2

## Current State (Updated 2026-01-16)

Phase 1 of the control loop architecture is complete ([CONTROL_LOOP_PHASE1_COMPLETE.md](CONTROL_LOOP_PHASE1_COMPLETE.md)), but **not yet integrated** into the runtime.

### ✅ What Works Now (As of 2026-01-16)

`Human.approve()` **DOES work** using the old `CLIHITLHandler`:
- Shows Rich-formatted CLI prompts
- Blocking stdin input
- Single-channel only (no omnichannel racing)
- No checkpoint/resume on HITL waits

### ⏳ What Phase 2 Will Enable

Integration of the new `ControlLoopHandler` will add:
- **Omnichannel racing**: Send to ALL enabled channels (CLI + Cloud + Slack), first response wins
- **Exit-and-resume pattern**: Save state when waiting, resume on restart
- **Rich context**: Full conversation history, prior interactions, procedure metadata
- **Interruptible CLI**: Can be cancelled if another channel responds first

### Why Integration Is Needed

1. The new `ControlLoopHandler` exists but isn't being used
2. The `HumanPrimitive` calls `execution_context.wait_for_human()`
3. `ExecutionContext.wait_for_human()` delegates to the old `HITLHandler` protocol
4. The `TactusRuntime` is initialized with old `CLIHITLHandler`, not new `ControlLoopHandler`

## Integration Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Lua DSL Layer                                                │
│   Human.approve({message = "..."})                          │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      v
┌─────────────────────────────────────────────────────────────┐
│ HumanPrimitive (tactus/primitives/human.py)                 │
│   - Validates options                                        │
│   - Converts Lua tables to Python dicts                     │
│   - Calls execution_context.wait_for_human()                │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      v
┌─────────────────────────────────────────────────────────────┐
│ ExecutionContext (tactus/core/execution_context.py)         │
│   - Creates HITLRequest from parameters                     │
│   - Enriches with procedure context                         │
│   - Delegates to control_handler                            │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      v
┌─────────────────────────────────────────────────────────────┐
│ ControlLoopHandler (tactus/adapters/control_loop.py)        │
│   - Loads enabled channels from config                      │
│   - Creates ControlRequest with rich context                │
│   - Sends to ALL channels concurrently                      │
│   - Waits for first response                                │
│   - Cancels other channels                                  │
│   - Converts ControlResponse -> HITLResponse                │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      v (to all enabled channels)
┌─────────────────────────────────────────────────────────────┐
│ Control Channels                                             │
│   ├─ CLIControlChannel (background thread, interruptible)   │
│   ├─ SSEControlChannel (Flask IDE server) [Phase 3]         │
│   └─ TactusCloudChannel (WebSocket API) [Phase 5]           │
└─────────────────────────────────────────────────────────────┘
```

## Integration Tasks

### Task 1: Update ExecutionContext to Use ControlLoopHandler

**File:** `tactus/core/execution_context.py`

**Current implementation (lines 287-317):**
```python
def wait_for_human(
    self,
    request_type: str,
    message: str,
    timeout_seconds: Optional[int],
    default_value: Any,
    options: Optional[List[dict]],
    metadata: dict,
) -> HITLResponse:
    """Wait for human response using the configured HITL handler."""
    if not self.hitl:
        # No HITL handler - return default immediately
        return HITLResponse(
            value=default_value, responded_at=datetime.now(timezone.utc), timed_out=True
        )

    # Create HITL request
    request = HITLRequest(
        request_type=request_type,
        message=message,
        timeout_seconds=timeout_seconds,
        default_value=default_value,
        options=options,
        metadata=metadata,
    )

    # Delegate to HITL handler (may raise ProcedureWaitingForHuman)
    return self.hitl.request_interaction(self.procedure_id, request, self)
```

**Changes needed:**

1. Rename `self.hitl` to `self.control_handler` (or keep both for transition)
2. Check for new control handler first, fall back to old HITL handler
3. Enrich request with procedure context before delegating
4. Convert between old HITLRequest and new ControlRequest formats

**Proposed implementation:**
```python
def wait_for_human(
    self,
    request_type: str,
    message: str,
    timeout_seconds: Optional[int],
    default_value: Any,
    options: Optional[List[dict]],
    metadata: dict,
) -> HITLResponse:
    """Wait for human response using control loop or legacy HITL handler."""

    # Try new control loop handler first
    control_handler = getattr(self, 'control_handler', None)
    if control_handler is not None:
        return self._wait_for_human_via_control_loop(
            request_type, message, timeout_seconds, default_value, options, metadata
        )

    # Fall back to legacy HITL handler
    if self.hitl:
        request = HITLRequest(
            request_type=request_type,
            message=message,
            timeout_seconds=timeout_seconds,
            default_value=default_value,
            options=options,
            metadata=metadata,
        )
        return self.hitl.request_interaction(self.procedure_id, request, self)

    # No handler - return default immediately
    return HITLResponse(
        value=default_value, responded_at=datetime.now(timezone.utc), timed_out=True
    )

def _wait_for_human_via_control_loop(
    self,
    request_type: str,
    message: str,
    timeout_seconds: Optional[int],
    default_value: Any,
    options: Optional[List[dict]],
    metadata: dict,
) -> HITLResponse:
    """Use new control loop handler with rich context."""
    from tactus.protocols.control import ControlRequest, ControlRequestType

    # Map old request_type strings to new enum
    request_type_map = {
        "approval": ControlRequestType.APPROVAL,
        "input": ControlRequestType.INPUT,
        "review": ControlRequestType.REVIEW,
        "escalation": ControlRequestType.ESCALATION,
    }

    # Create rich control request
    control_request = ControlRequest(
        request_id=f"req_{uuid.uuid4().hex[:8]}",
        procedure_id=self.procedure_id,
        procedure_name=self.metadata.get("procedure_name", "unknown"),
        invocation_id=self.metadata.get("invocation_id", "unknown"),
        namespace=self.metadata.get("namespace", "default"),
        subject=self.metadata.get("subject"),
        started_at=self.metadata.get("started_at", datetime.now(timezone.utc)),
        elapsed_seconds=int(time.time() - self.metadata.get("started_at_timestamp", time.time())),
        request_type=request_type_map.get(request_type, ControlRequestType.INPUT),
        message=message,
        options=self._convert_options_to_control_format(options),
        input_summary=self.metadata.get("input_summary", {}),
        conversation=self._get_conversation_history(),
        prior_interactions=self._get_prior_control_interactions(),
        metadata=metadata,
    )

    # Delegate to control loop handler (may raise ProcedureWaitingForHuman)
    control_response = self.control_handler.request_interaction(
        self.procedure_id, control_request, self
    )

    # Convert ControlResponse back to HITLResponse
    return HITLResponse(
        value=control_response.value,
        responded_at=control_response.timestamp,
        responded_by=control_response.channel_id,
        timed_out=False,
    )
```

**Context methods to add:**
```python
def _get_conversation_history(self) -> List[ConversationMessage]:
    """Get conversation history for control requests."""
    # TODO: Implement based on how runtime tracks conversation
    return []

def _get_prior_control_interactions(self) -> List[ControlInteraction]:
    """Get prior control interactions in this invocation."""
    # TODO: Implement based on checkpoint log
    return []

def _convert_options_to_control_format(self, options: Optional[List[dict]]) -> List[ControlOption]:
    """Convert legacy options format to ControlOption."""
    from tactus.protocols.control import ControlOption
    if not options:
        return []
    return [
        ControlOption(
            label=opt.get("label", ""),
            value=opt.get("value"),
            type=opt.get("type", "action"),
        )
        for opt in options
    ]
```

### Task 2: Update TactusRuntime to Accept ControlLoopHandler

**File:** `tactus/core/runtime.py`

**Current constructor (around line 69-75):**
```python
def __init__(
    self,
    procedure_id: str,
    storage_backend: Optional[StorageBackend] = None,
    hitl_handler: Optional[HITLHandler] = None,
    chat_recorder: Optional[ChatRecorder] = None,
    mcp_server=None,
    mcp_servers: Optional[Dict[str, Any]] = None,
    ...
):
```

**Changes needed:**

1. Add `control_handler` parameter
2. Pass control_handler to ExecutionContext
3. Update default instantiation to create ControlLoopHandler from config

**Proposed changes:**
```python
def __init__(
    self,
    procedure_id: str,
    storage_backend: Optional[StorageBackend] = None,
    hitl_handler: Optional[HITLHandler] = None,  # Legacy, optional
    control_handler: Optional[Any] = None,  # New control loop handler
    chat_recorder: Optional[ChatRecorder] = None,
    ...
):
    # If no control_handler provided, try to create from config
    if control_handler is None:
        control_handler = self._create_default_control_handler(storage_backend)

    # Create execution context with both handlers (for transition)
    self.execution_context = BaseExecutionContext(
        procedure_id=procedure_id,
        storage=storage_backend or MemoryStorage(),
        hitl=hitl_handler,  # Legacy
        control_handler=control_handler,  # New
        log_handler=self.log_handler,
    )

def _create_default_control_handler(self, storage_backend):
    """Create control loop handler from configuration."""
    from tactus.core.config_manager import get_config
    from tactus.adapters.control_loop import ControlLoopHandler
    from tactus.adapters.channels import load_default_channels

    config = get_config()

    # Check if control loop is enabled
    control_config = config.get("control", {})
    if not control_config.get("enabled", False):
        logger.info("Control loop disabled in config")
        return None

    # Load channels from config
    channels = load_default_channels()

    if not channels:
        logger.warning("Control loop enabled but no channels available")
        return None

    logger.info(f"Control loop enabled with {len(channels)} channels: {[c.channel_id for c in channels]}")

    return ControlLoopHandler(
        channels=channels,
        storage=storage_backend,
    )
```

### Task 3: Update BaseExecutionContext Constructor

**File:** `tactus/core/execution_context.py`

**Current constructor (around line 107-134):**
```python
def __init__(
    self,
    procedure_id: str,
    storage: StorageBackend,
    hitl: Optional[HITLHandler] = None,
    chat_recorder: Optional[ChatRecorder] = None,
    log_handler: Optional[Any] = None,
):
    self.procedure_id = procedure_id
    self.storage = storage
    self.hitl = hitl
    ...
```

**Changes needed:**
```python
def __init__(
    self,
    procedure_id: str,
    storage: StorageBackend,
    hitl: Optional[HITLHandler] = None,  # Legacy
    control_handler: Optional[Any] = None,  # New
    chat_recorder: Optional[ChatRecorder] = None,
    log_handler: Optional[Any] = None,
):
    self.procedure_id = procedure_id
    self.storage = storage
    self.hitl = hitl  # Legacy
    self.control_handler = control_handler  # New
    ...
```

### Task 4: Enable Control Loop in Default Configuration

**File:** `tactus/core/config_manager.py`

**Changes needed:**

Update default configuration to enable control loop:

```python
# In get_default_config() or similar:
"control": {
    "enabled": True,  # Enable by default
    "channels": {
        "cli": {
            "enabled": "auto",  # Auto-detect based on tty
        }
    }
}
```

### Task 5: Update CLI Entry Point

**File:** `tactus/cli/app.py` (or wherever tactus command is defined)

**Changes needed:**

Ensure that when running via CLI, the control loop is enabled by default:

```python
# When creating TactusRuntime for CLI execution:
runtime = TactusRuntime(
    procedure_id=procedure_id,
    storage_backend=storage,
    # Don't pass hitl_handler - let it auto-create control_handler
    control_handler=None,  # Will be created from config
)
```

### Task 6: Test Integration

Create a simple test to verify the integration:

**File:** `tests/control_loop/test_integration.py`

```python
"""Test control loop integration with runtime."""
import pytest
from tactus.core.runtime import TactusRuntime
from tactus.adapters.memory import MemoryStorage
from tactus.adapters.control_loop import ControlLoopHandler
from tactus.adapters.channels.cli import CLIControlChannel


def test_control_loop_integration_smoke():
    """Smoke test: runtime can be created with control loop handler."""
    storage = MemoryStorage()
    channels = [CLIControlChannel()]
    control_handler = ControlLoopHandler(channels=channels, storage=storage)

    runtime = TactusRuntime(
        procedure_id="test_proc",
        storage_backend=storage,
        control_handler=control_handler,
    )

    assert runtime.execution_context.control_handler is not None
    assert runtime.execution_context.control_handler == control_handler


def test_human_primitive_uses_control_loop():
    """Test that Human.approve() uses control loop when configured."""
    # TODO: Implement when integration is complete
    pass
```

## Metadata Requirements

For the control loop to provide rich context, the runtime needs to track:

1. **`procedure_name`** - Human-readable procedure name
2. **`invocation_id`** - Unique ID for this invocation
3. **`namespace`** - For routing/authorization (e.g., "operations/incidents/level3")
4. **`subject`** - Human-readable identifier (e.g., "Customer: John Doe")
5. **`started_at`** - When the procedure started
6. **`input_summary`** - Key fields from procedure input to display to controllers
7. **Conversation history** - Full conversation with tool calls
8. **Prior control interactions** - Previous HITL decisions in this invocation

### Where to Set Metadata

These should be set when the runtime is initialized or during procedure execution:

```python
# In TactusRuntime.__init__ or when loading procedure:
self.execution_context.metadata.update({
    "procedure_name": procedure_name,  # From registry
    "invocation_id": str(uuid.uuid4()),
    "namespace": procedure_config.get("namespace", "default"),
    "started_at": datetime.now(timezone.utc),
    "started_at_timestamp": time.time(),
})

# When procedure is called with input:
self.execution_context.metadata["input_summary"] = self._extract_input_summary(input_data)
self.execution_context.metadata["subject"] = self._extract_subject(input_data)

# As conversation progresses:
# Track conversation history in execution context
```

### Input Summary Extraction

The `input_summary` should extract key fields for display:

```python
def _extract_input_summary(self, input_data: Dict[str, Any], max_fields: int = 5) -> Dict[str, Any]:
    """Extract key fields from input for display to controllers."""
    if not isinstance(input_data, dict):
        return {}

    # Simple heuristic: take first N fields
    # TODO: Could be smarter based on schema or field importance
    summary = {}
    for i, (key, value) in enumerate(input_data.items()):
        if i >= max_fields:
            break
        # Truncate long values
        if isinstance(value, str) and len(value) > 50:
            summary[key] = value[:47] + "..."
        else:
            summary[key] = value

    return summary
```

### Subject Extraction

The `subject` provides a human-readable identifier:

```python
def _extract_subject(self, input_data: Dict[str, Any]) -> Optional[str]:
    """Extract subject from input data for display."""
    if not isinstance(input_data, dict):
        return None

    # Common subject field names
    subject_fields = ["name", "subject", "customer_name", "user_name", "email", "id"]

    for field in subject_fields:
        if field in input_data:
            value = input_data[field]
            if isinstance(value, str):
                return value
            return str(value)

    return None
```

## Testing the Integration

Once integration is complete, test with:

```bash
# 1. Run the simple HITL example
tactus examples/90-hitl-simple.tac

# Expected: CLI prompts appear with rich context
# - Procedure name
# - Input summary (if any)
# - Prior interactions (if any)
# - Formatted approval/input/review prompts

# 2. Verify control loop is being used
# Add logging to see:
# - "Control loop enabled with 1 channels: ['cli']"
# - "CLIControlChannel: sending notification"
# - "CLIControlChannel: received response"

# 3. Test interruption (if implementing multi-channel)
# - Run with both CLI and another channel enabled
# - Respond from one channel
# - Verify other channel shows "✓ Responded via {channel}"
```

## Migration Path

Since the user stated **no backward compatibility is needed**, we can migrate cleanly:

### Option A: Clean Break (Recommended)

1. Implement all tasks above
2. Remove old `HITLHandler` protocol references
3. Update all examples to use new control loop
4. Delete `tactus/adapters/cli_hitl.py` (old CLI HITL)

### Option B: Gradual Transition (If Needed)

1. Implement tasks with both handlers supported
2. Default to control loop, fall back to HITL
3. Deprecate old HITL system in documentation
4. Remove in future version

Since user wants clean slate, **Option A is recommended**.

## Summary

To integrate the control loop:

1. ✅ **Phase 1 complete** - Architecture, channels, control loop handler implemented
2. ⏳ **Phase 2 (this document)** - Integrate with runtime:
   - Update `ExecutionContext.wait_for_human()` to use `ControlLoopHandler`
   - Add `control_handler` parameter to `TactusRuntime`
   - Create default control handler from config
   - Track rich context metadata (procedure_name, subject, etc.)
   - Enable control loop in default config
3. ⏳ **Testing** - Verify HITL prompts appear in examples
4. ⏳ **Cleanup** - Remove old HITL system

Once Phase 2 is complete, `Human.approve()` will work with the new control loop and display rich CLI prompts.
