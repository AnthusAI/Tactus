# Omnichannel HITL Notification Architecture - Planning Document

## Status Update (2026-01-22)

### ✅ Phase 1 COMPLETE
Core control loop architecture implemented:
- Control protocol and models ([tactus/protocols/control.py](../tactus/protocols/control.py))
- InProcessChannel and HostControlChannel base classes
- CLIControlChannel with Rich formatting
- ControlLoopHandler with racing pattern (all channels race, first wins)
- Configuration support and channel auto-detection
- See [archive/CONTROL_LOOP_PHASE1_COMPLETE.md](archive/CONTROL_LOOP_PHASE1_COMPLETE.md) (archived)

### ✅ Plain Function Support COMPLETE
Fixed runtime to support both DSL and plain Lua syntax:
- Auto-registration of `function main()` definitions
- Script mode transformation skips files with named functions
- HITL examples (90-hitl-simple.tac) now work correctly
- See [archive/HITL_FIX_SUMMARY.md](archive/HITL_FIX_SUMMARY.md) (archived)

### ✅ Phase 2 COMPLETE - Runtime Integration
All goals achieved (2026-01-19):
- ✅ ControlLoopHandler replaces CLIHITLHandler in runtime (via ControlLoopHITLAdapter)
- ✅ ExecutionContext.wait_for_human() uses new control loop
- ✅ Exit-and-resume pattern with ProcedureWaitingForHuman exception
- ✅ Storage methods for pending HITL requests with deterministic IDs
- ✅ Rich context metadata (procedure_name, invocation_id, subject, started_at, input_summary, conversation_history, prior_control_interactions)
- ✅ Human.inputs() batched HITL feature with CLI support
- See [archive/CONTROL_LOOP_INTEGRATION.md](archive/CONTROL_LOOP_INTEGRATION.md) (archived)

### ✅ Phase 3 COMPLETE - IDE/SSE Channel with Container Support
All goals achieved (2026-01-21):
- ✅ SSEControlChannel implemented for IDE notifications
- ✅ Flask GET /api/hitl/stream endpoint for SSE events
- ✅ Flask POST /api/hitl/response/<request_id> endpoint for responses
- ✅ Web IDE UI for HITL panels with approval/reject buttons
- ✅ Multi-channel racing (CLI + IDE) working
- ✅ BrokerControlChannel for container → host HITL bridging
- ✅ Real-time event streaming from containers via background thread worker
- ✅ Generalized LLM backend config (provider-agnostic infrastructure)
- ✅ Agent responses stream in real-time to IDE frontend
- ✅ Protocol capabilities extended (supports_select, supports_inputs, supports_upload)
- ✅ Frontend emoji cleanup (replaced with icon components)
- See commit a6e49ff "feat: enable real-time container HITL and event streaming"

### ✅ Phase 4 COMPLETE - Unified HITL Component Architecture
**Completion Date: 2026-01-24**

All goals achieved:
- ✅ Human.approve(), input(), select() work in both containers and direct execution
- ✅ Multi-channel racing (CLI + IDE) working
- ✅ Checkpoint/resume across HITL waits working
- ✅ Real-time event streaming validated
- ✅ **Unified component registry architecture** implemented
- ✅ **Batched inputs (Human.inputs())** with inline and modal modes
- ✅ **Config-driven UI behavior** (inline as default, modal as optional)
- ✅ **Component registry** with three-tier system (Built-in < Standard Library < Application)
- ✅ **Modal cancellation handling** with reopen capability
- ✅ **Visual feedback** for multi-select, selected states
- ✅ **Form validation** for boolean, array, string, null/undefined
- ✅ **Response display** showing submitted values with labels

See commits:
- a6e49ff "feat: enable real-time container HITL and event streaming"
- 392660c "feat: add modal cancellation handling with reopen capability"

### ✅ Phase 4.1 COMPLETE - Unified Registry Architecture
**Completion Date: 2026-01-24**

**Goal Achieved:** 100% unified component architecture across inline and modal modes

What was accomplished:
- ✅ Registry infrastructure (`registry.ts`, `types.ts`)
- ✅ Built-in components extracted (`ApprovalComponent`, `InputComponent`, `SelectComponent`)
- ✅ Standard library components (`ImageSelectorComponent`)
- ✅ Public API (`hitlRegistry.register()`, `override()`, `listAvailable()`)
- ✅ Single-item requests use registry
- ✅ Batched inputs inline mode uses registry via `renderFormItem()`
- ✅ **Batched inputs modal mode uses registry**
- ✅ **InputComponent fixed** - Now captures text on every keystroke for batched inputs

**Key Changes:**
- Replaced 66 lines of hard-coded modal rendering with single `renderFormItem()` call
- Fixed InputComponent to use controlled input with onChange for real-time value capture
- Removed unused icon imports
- Modal and inline modes now use identical rendering logic
- Custom components will work in modal mode
- Single source of truth for all component rendering

**Impact:**
- ✅ Zero code duplication between inline and modal
- ✅ Changes to components only need to happen once
- ✅ Fully extensible architecture for custom components
- ✅ Easier maintenance and debugging
- ✅ Text inputs work correctly in batched mode (inline and modal)

See commits: 4005ae7, [pending commit for InputComponent fix]

### ✅ Phase 4.2 COMPLETE - API Cleanup
**Completion Date: 2026-01-24**

**Goal:** Improve API naming clarity by introducing `Human.multiple()` as primary method for batched inputs

**Tasks:**
- ✅ Add `Human.multiple()` method to primitives/human.py
- ✅ Deprecate `Human.inputs()` with logger warning
- ✅ Create `92-test-multiple.tac` example using new API
- ✅ Update module docstring to list `Human.multiple()` and mark `inputs()` as deprecated
- ✅ Add deprecation note in docstrings

**Key Changes:**
- Added `Human.multiple()` as the new primary method (delegates to `inputs()` internally)
- `Human.inputs()` now logs deprecation warning on every call
- Updated module docstring to list `Human.multiple()` and mark `inputs()` as deprecated
- Created `92-test-multiple.tac` example using the new API
- Original `92-test-inputs.tac` remains for backward compatibility testing

**Rationale:**
- "multiple" more clearly communicates collecting multiple inputs in one interaction
- Avoids confusion with singular "input" method
- Maintains backward compatibility via deprecation warning
- Allows gradual migration of existing procedures

### ⏳ Phase 4.3 PLANNED - Component Styling & Polish
**Status:** Planned for next session (2026-01-25)

**Goal:** Perfect styling and layouts of existing components before creating new ones

**Tasks:**
- [ ] Review and refine built-in component styling (Approval, Input, Select)
- [ ] Ensure consistent spacing, borders, colors across components
- [ ] Improve mobile responsiveness
- [ ] Polish inline vs modal rendering differences
- [ ] Add hover states and transitions
- [ ] Review accessibility (keyboard navigation, ARIA labels)

**Rationale:** Get the foundation perfect before building more standard library components

### ⏳ Phase 5 FUTURE - Standard Library Components
**Status:** Blocked on Phase 4.3 completion

Standard library components to create (after styling is perfected):
- TextOptionsSelectorComponent (Priority: HIGH) - Options with descriptions, card-based UI
- MultiChoiceApprovalComponent (Priority: MEDIUM) - Custom action buttons
- DatePickerComponent (Priority: LOW)
- ColorPickerComponent (Priority: LOW)

### ⏳ Phase 6 FUTURE - Documentation & Testing
Remaining work:
- Human.review() - Implemented but needs comprehensive testing
- Human.escalate() - Implemented but needs comprehensive testing
- Timeout behavior - Logic exists but needs thorough testing
- Documentation: Create CUSTOM_HITL_COMPONENTS.md guide
- Test suite expansion (93-test-*.tac series)

See "Testing Plan" section below for detailed checklist

---

## Original Planning Document

This document outlines the planned architecture for omnichannel Human-in-the-Loop (HITL) notifications in Tactus.

## Problem Statement

When Tactus procedures pause waiting for human input (approval, review, input, escalation), users need to be notified across multiple channels:
- Slack/Discord/Teams for team notifications
- Mobile push notifications
- Email for escalations
- IDE notifications for local development
- Custom integrations (SQS, webhooks, proprietary APIs)

Currently, Tactus only supports CLI-based HITL interactions.

## Design Principles

### Transport Agnostic

The architecture must be **completely pluggable and transport-agnostic**. Channels are not tied to any specific protocol:
- Not just webhooks
- Not just WebSockets
- Not just polling
- It can be **anything**

Each channel implementation decides how it communicates with its external service. The core protocol only cares about sending requests and receiving responses.

### Event-Driven Model

Channels follow an event-driven pattern:
- `send(request)` - Push a notification to the channel
- `receive() -> AsyncIterator[Response]` - Yield responses as they arrive via callbacks

The runtime doesn't care how a channel receives responses - it could be:
- Webhook callback from Slack
- WebSocket message from Discord
- Polling an SQS queue
- HTTP long-polling
- gRPC stream
- Anything else

### Namespace-Based Routing (Publish-Subscribe Model)

Control requests include a `namespace` field that channels interpret for routing and authorization. This is fundamentally a **publish-subscribe** pattern:

**Core Concept:**
```
namespace: "operations/incidents/level3-or-level4"
```

- **Publishers**: Tactus runtimes emit control requests to namespaces
- **Subscribers**: Clients subscribe to namespace patterns they're interested in
- **Responders**: A subset of subscribers authorized to provide input

**Subscriber Modes:**
- `observe` - Read-only access (dashboards, audit logs, monitoring systems)
- `respond` - Can see AND provide input (authorized controllers)

**Example routing:**
```
Namespace: "operations/incidents/level3-or-level4"

Subscribers:
├─ Level 0 Dashboard (observe) - sees traffic, cannot respond
├─ Level 1 Dashboard (observe) - sees traffic, cannot respond
├─ Level 3 Operator App (respond) - can see AND respond
├─ Level 4 Operator App (respond) - can see AND respond
└─ Audit System (observe) - logs everything, never responds
```

**Key properties:**
- Namespace is an **opaque string** - channels interpret it however they want
- CLI channel ignores namespace (local-only)
- Tactus Cloud parses it for routing and authorization
- Slack could map namespace segments to channels
- Channels decide whether responses are accepted based on subscriber mode

**Collaboration features enabled:**
- "3 people are viewing this request"
- "Sarah is typing a response..."
- Real-time updates when someone responds

**Use cases:**
- **Authorization without crypto**: Level 0 operators can't respond to Level 3+ requests
- **Read-only dashboards**: Team leads monitor operations without being prompted to act
- **Audit systems**: Log all control requests without participating
- **Multi-team routing**: `finance/refunds/*` goes to finance team, `ops/incidents/*` goes to ops

### Eager Initialization

Channels initialize when the procedure starts, not when an HITL interaction occurs. This avoids blocking on slow channel startup (Discord bot connection, OAuth handshakes, etc.) when a human response is needed quickly.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         TACTUS RUNTIME                                   │
│                                                                          │
│  Procedure starts                                                        │
│       ↓                                                                  │
│  ChannelManager.initialize_all()  ← Eager init, non-blocking            │
│       ↓                                                                  │
│  ... procedure executes ...                                              │
│       ↓                                                                  │
│  Human.approve() → MultichannelHITLHandler                              │
│                           ↓                                              │
│              ┌────────────┼────────────┐                                 │
│              ↓            ↓            ↓                                 │
│         SlackChannel  SQSChannel  EmailChannel                          │
│         (in-process)  (in-process) (in-process)                         │
│              │            │            │                                 │
│              └────────────┼────────────┘                                 │
│                           ↓                                              │
│              Save state to StorageBackend                                │
│              Raise ProcedureWaitingForHuman                              │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
                           │ (Runtime exits cleanly)
                           ↓
┌──────────────────────────────────────────────────────────────────────────┐
│                    CHANNEL RESPONSE HANDLING                             │
│                                                                          │
│   Each channel receives responses in its own way:                        │
│                                                                          │
│   SlackChannel:    Webhook POST to /slack/interactivity                  │
│   SQSChannel:      Polls queue in asyncio task                           │
│   DiscordChannel:  WebSocket message (future daemon)                     │
│   EmailChannel:    Fire-and-forget (no response expected)                │
│                                                                          │
│   All responses flow to → ResponseAggregator                             │
│                                ↓                                         │
│                         First response wins                              │
│                         Cancel other channels                            │
│                         Resume procedure                                 │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

## Core Protocol

### NotificationChannel Protocol

```python
class NotificationChannel(Protocol):
    """
    Protocol for notification channel plugins.

    Transport-agnostic: implementations decide how to communicate
    with their external services.
    """

    @property
    def channel_id(self) -> str:
        """Unique identifier (e.g., 'slack', 'discord', 'sqs')."""
        ...

    @property
    def capabilities(self) -> ChannelCapabilities:
        """What this channel supports."""
        ...

    async def initialize(self) -> None:
        """
        Initialize the channel (connect, authenticate, etc.).
        Called eagerly at procedure start, not at HITL point.
        """
        ...

    async def send(
        self,
        procedure_id: str,
        request_id: str,
        request: HITLRequest,
    ) -> NotificationDeliveryResult:
        """Send HITL notification to this channel."""
        ...

    async def receive(self) -> AsyncIterator[HITLResponse]:
        """
        Yield responses as they arrive.

        How responses arrive is channel-specific:
        - Webhook handler pushes to internal queue
        - Polling task fetches from external queue
        - WebSocket handler receives messages
        """
        ...

    async def cancel(self, external_message_id: str, reason: str) -> None:
        """Update/cancel notification when resolved via another channel."""
        ...

    async def shutdown(self) -> None:
        """Clean shutdown (disconnect, cleanup)."""
        ...
```

### Channel Base Classes

**InProcessChannel** - For channels that work well with asyncio:

```python
class InProcessChannel(ABC):
    """
    Base class for channels that run in-process with asyncio.

    Suitable for:
    - HTTP webhooks (Slack, Teams)
    - Queue polling (SQS, Redis)
    - Email (SMTP send, IMAP poll)
    - Simple HTTP APIs

    These channels coexist happily with the asyncio event loop
    and don't need separate processes.
    """

    async def initialize(self) -> None:
        """Default: no-op. Override for auth handshakes, etc."""
        pass

    @abstractmethod
    async def send(self, ...) -> NotificationDeliveryResult:
        """Subclass implements channel-specific send."""
        ...

    async def receive(self) -> AsyncIterator[HITLResponse]:
        """
        Default implementation: yield from internal response queue.
        Webhook handlers push to this queue.
        Override for polling-based channels.
        """
        while True:
            response = await self._response_queue.get()
            yield response
```

**DaemonChannel** (Future) - For channels needing persistent connections:

```python
class DaemonChannel(ABC):
    """
    Base class for channels that need separate daemon processes.

    Future implementation for:
    - Discord (persistent WebSocket to gateway)
    - Real-time chat protocols
    - Heavy services that shouldn't block procedure execution

    Uses broker-style IPC (length-prefixed JSON over TCP).
    See tactus/broker/ for reference implementation.
    """
    # YAGNI for now - document for future reference
```

## IDE/SSE Channel - Detailed Design (HIGHEST PRIORITY)

### Why IDE/SSE is the First Channel

- ✅ **Reuses existing infrastructure** - SSE streaming already implemented in Flask
- ✅ **No new services needed** - Flask API already running for IDE
- ✅ **Event-driven in both directions** - SSE (server→client) + HTTP POST (client→server)
- ✅ **Primary development environment** - Where all development and testing happens
- ✅ **Proves the architecture** - Validates plugin system before building cloud services
- ✅ **Immediately useful** - Developers can test HITL workflows instantly

### Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                  VSCode Extension (IDE)                           │
│  - Connected to Flask /stream endpoint via SSE                    │
│  - Receives hitl.request events with full context                │
│  - Displays HITL panel/webview                                    │
│  - POSTs responses to /hitl/response/<request_id>                │
└────────────────────┬─────────────────────────────────────────────┘
                     │ SSE (server → client)
                     │ HTTP POST (client → server)
                     ↓
┌──────────────────────────────────────────────────────────────────┐
│              Flask API (tactus.ide.server)                        │
│  - Existing /stream endpoint for SSE                              │
│  - NEW: hitl.request event type                                   │
│  - NEW: POST /hitl/response/<request_id> endpoint                │
│  - Integrates SSENotificationChannel with runtime                │
└────────────────────┬─────────────────────────────────────────────┘
                     │
                     ↓
┌──────────────────────────────────────────────────────────────────┐
│             SSENotificationChannel (NEW)                          │
│  - InProcessChannel implementation                                │
│  - send(): Pushes hitl.request to SSE stream                     │
│  - receive(): Yields responses from internal queue               │
│  - handle_ide_response(): Flask calls this on POST               │
└────────────────────┬─────────────────────────────────────────────┘
                     │
                     ↓
┌──────────────────────────────────────────────────────────────────┐
│                 MultichannelHITLHandler                           │
│  - Gathers context from ExecutionContext                          │
│  - Creates rich HITLRequest with conversation, history           │
│  - Sends to SSENotificationChannel                               │
│  - Raises ProcedureWaitingForHuman                               │
└──────────────────────────────────────────────────────────────────┘
```

### SSENotificationChannel Implementation

```python
# tactus/adapters/channels/ide_sse.py

class SSENotificationChannel(InProcessChannel):
    """
    Server-Sent Events channel for IDE integration.

    Reuses existing Flask SSE infrastructure. No daemon, no new services.
    """

    def __init__(self, sse_manager):
        super().__init__()
        self.sse_manager = sse_manager  # Existing SSE event manager

    @property
    def channel_id(self) -> str:
        return "ide"

    @property
    def capabilities(self) -> ChannelCapabilities:
        return ChannelCapabilities(
            supports_approval=True,
            supports_input=True,
            supports_review=True,
            supports_escalation=True,
            supports_interactive_buttons=True,
            max_message_length=None,
        )

    async def initialize(self) -> None:
        logger.info(f"{self.channel_id}: initializing...")
        # No-op - SSE already set up by Flask
        logger.info(f"{self.channel_id}: ready")

    async def send(
        self,
        procedure_id: str,
        request_id: str,
        request: HITLRequest,
    ) -> NotificationDeliveryResult:
        logger.info(f"{self.channel_id}: sending notification for {request_id}")

        # Send SSE event to IDE with full context
        self.sse_manager.send_event({
            'type': 'hitl.request',
            'request_id': request_id,

            # Identity
            'procedure_id': procedure_id,
            'procedure_name': request.procedure_name,
            'invocation_id': request.invocation_id,
            'subject': request.subject,
            'started_at': request.started_at.isoformat(),
            'elapsed_seconds': request.elapsed_seconds,

            # Input summary
            'input_summary': request.input_summary,

            # The question
            'request_type': request.request_type,
            'message': request.message,
            'options': [
                {'label': opt.label, 'value': opt.value, 'style': opt.style}
                for opt in request.options
            ],

            # Full context for decision-making
            'conversation': [
                {
                    'role': msg.role,
                    'content': msg.content,
                    'timestamp': msg.timestamp.isoformat(),
                    'tool_name': msg.tool_name,
                    'tool_input': msg.tool_input,
                    'tool_output': msg.tool_output,
                }
                for msg in request.conversation
            ],

            # Prior HITL interactions
            'prior_hitl': [
                {
                    'message': h.request.message,
                    'response': h.response.value,
                    'responded_by': h.responded_by,
                    'responded_at': h.responded_at.isoformat(),
                }
                for h in request.prior_hitl
            ],
        })

        return NotificationDeliveryResult(
            channel_id=self.channel_id,
            external_message_id=request_id,
            delivered_at=datetime.now(timezone.utc),
            success=True,
        )

    async def receive(self) -> AsyncIterator[HITLResponse]:
        """Yield responses as they arrive from Flask POST handler."""
        while True:
            response = await self._response_queue.get()
            logger.info(f"{self.channel_id}: received response for {response.request_id}")
            yield response

    def handle_ide_response(self, request_id: str, value: Any):
        """
        Called by Flask POST endpoint when IDE sends response.

        This is the bridge from Flask's synchronous HTTP handler
        to the async channel protocol.
        """
        self._response_queue.put_nowait(HITLResponse(
            request_id=request_id,
            value=value,
            responded_at=datetime.now(timezone.utc),
            timed_out=False,
        ))
```

### Flask Integration

```python
# tactus/ide/server.py (modifications)

from tactus.adapters.channels.ide_sse import SSENotificationChannel

# Initialize SSE channel (at startup)
sse_channel = SSENotificationChannel(sse_manager)

# Wire into runtime
runtime_config = {
    'hitl_handler': MultichannelHITLHandler(
        channels=[sse_channel],
        storage=storage_backend,
    )
}

@app.get('/stream')
def stream():
    """Existing SSE endpoint - no changes needed!"""
    def generate():
        # Existing event streaming logic
        # SSE manager handles all event types including hitl.request
        for event in sse_manager.events():
            yield f"data: {json.dumps(event)}\n\n"

    return Response(generate(), mimetype='text/event-stream')

# NEW endpoint for HITL responses
@app.post('/hitl/response/<request_id>')
def hitl_response(request_id: str):
    """IDE posts responses here."""
    try:
        value = request.json.get('value')

        # Push to SSE channel's internal queue
        sse_channel.handle_ide_response(request_id, value)

        return {'status': 'ok', 'request_id': request_id}
    except Exception as e:
        logger.exception(f"Error handling HITL response for {request_id}")
        return {'status': 'error', 'message': str(e)}, 400
```

### IDE UI (VSCode Extension)

```typescript
// VSCode extension - listen for SSE events

const eventSource = new EventSource('http://localhost:5000/stream');

eventSource.addEventListener('message', (event) => {
  const data = JSON.parse(event.data);

  if (data.type === 'hitl.request') {
    showHITLPanel({
      requestId: data.request_id,
      procedureName: data.procedure_name,
      subject: data.subject,
      message: data.message,
      options: data.options,

      // Rich context
      conversationHistory: data.conversation,
      priorHITL: data.prior_hitl,
      inputSummary: data.input_summary,
      startedAt: new Date(data.started_at),
      elapsedSeconds: data.elapsed_seconds,
    });
  }
});

// User clicks "Approve" button
async function onApprove(requestId: string, value: any) {
  await fetch(`http://localhost:5000/hitl/response/${requestId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ value }),
  });
}

// HITL Panel UI (React/Vue/whatever)
function HITLPanel({ requestId, message, options, conversationHistory }) {
  return (
    <div className="hitl-panel">
      <h2>{procedureName}: {subject}</h2>
      <p className="elapsed">Started {formatTime(startedAt)} ago</p>

      <div className="message">{message}</div>

      {/* Collapsible conversation history */}
      <details>
        <summary>Conversation History ({conversationHistory.length} messages)</summary>
        <div className="conversation">
          {conversationHistory.map((msg, i) => (
            <div key={i} className={`message message-${msg.role}`}>
              {msg.role === 'tool' ? (
                <>
                  <strong>Tool:</strong> {msg.tool_name}({JSON.stringify(msg.tool_input)})
                  <br/>
                  <strong>Result:</strong> {JSON.stringify(msg.tool_output)}
                </>
              ) : (
                <>{msg.content}</>
              )}
            </div>
          ))}
        </div>
      </details>

      {/* Action buttons */}
      <div className="actions">
        {options.map((opt) => (
          <button
            key={opt.value}
            className={`btn btn-${opt.style}`}
            onClick={() => onApprove(requestId, opt.value)}
          >
            {opt.label}
          </button>
        ))}
      </div>
    </div>
  );
}
```

### Advantages of IDE/SSE Channel

1. **Zero infrastructure overhead** - Uses existing Flask SSE
2. **Fast iteration** - No deploy, no cloud services, instant feedback
3. **Perfect for development** - Exactly where developers work
4. **Proves the architecture** - If it works here, it'll work anywhere
5. **Simple debugging** - Can curl the POST endpoint manually

### Testing Flow

```bash
# 1. Start Flask server
tactus serve

# 2. In browser, open SSE stream
open http://localhost:5000/stream

# 3. Run procedure with HITL
tactus run examples/hitl-test.tac

# 4. See hitl.request event in browser console

# 5. Manually approve via curl
curl -X POST http://localhost:5000/hitl/response/req_abc123 \
  -H "Content-Type: application/json" \
  -d '{"value": true}'

# 6. Procedure resumes and completes
```

## Host App Integration (Embedded Control Channel)

### What This Is

The pattern for any app embedding Tactus to become a control channel. The CLI is just the simplest example - but this applies to any host app: web servers, desktop apps, Jupyter notebooks, etc. The host app is inherently connected since it's running the runtime.

**Terminology note:** We use "control loop" rather than "HITL" because controllers aren't always human. We also support model-in-the-loop (MITL) where another agent provides oversight.

### All Channels Race - First Response Wins

**Key insight:** There's no reason for the host app to block other channels. If you're at your terminal and walk away, you should be able to respond from your phone via Tactus Cloud.

**The model:**
1. **All enabled channels receive the request simultaneously** - host app, IDE, Cloud, etc.
2. **First response wins** - whichever channel gets a controller response first
3. **Other channels get cancelled** - dismiss prompts, update messages with "Responded via {channel}"

This means:
- You can respond at the terminal if you're there
- You can walk away and respond from your phone
- A model-in-the-loop controller can respond programmatically
- Whichever comes first wins

### Host App as an Interruptible Channel

The host app channel needs to be **interruptible** - it displays a prompt but can be cancelled if another channel responds first.

```python
# tactus/adapters/channels/host.py - Base class for host app channels
# tactus/adapters/channels/cli.py - CLI-specific implementation

class HostControlChannel(InProcessChannel):
    """
    Base class for host app control channels.

    Any app embedding Tactus can extend this to become a control channel.
    CLI is the simplest example, but this applies to any host app.

    Interruptible: if another channel responds first, the host app prompt
    is dismissed and shows "Responded via {channel}".
    """

    def __init__(self):
        super().__init__()
        self._cancel_event = asyncio.Event()
        self._input_thread: Optional[threading.Thread] = None

    @property
    def channel_id(self) -> str:
        return "cli"

    async def send(
        self,
        procedure_id: str,
        request_id: str,
        request: HITLRequest,
    ) -> NotificationDeliveryResult:
        """Display CLI prompt (non-blocking, interruptible)."""
        console = Console()

        # Display context
        console.print(f"\n[bold]{request.procedure_name}: {request.subject}[/bold]")
        console.print(f"Started {format_time_ago(request.started_at)} ago")

        if request.input_summary:
            console.print(Panel(yaml.dump(request.input_summary), title="Input Data"))

        if request.prior_hitl:
            console.print("\n[dim]Previous decisions:[/dim]")
            for h in request.prior_hitl:
                console.print(f"  • {h.responded_by}: {h.response}")

        console.print(f"\n[yellow]{request.message}[/yellow]")

        # Start background thread for stdin reading
        self._start_input_thread(request_id, request.options)

        return NotificationDeliveryResult(
            channel_id=self.channel_id,
            external_message_id=request_id,
            delivered_at=datetime.now(timezone.utc),
            success=True,
        )

    async def cancel(self, external_message_id: str, reason: str) -> None:
        """Cancel the CLI prompt - another channel responded first."""
        self._cancel_event.set()
        console = Console()
        console.print(f"\n[green]✓ {reason}[/green]")

    def _start_input_thread(self, request_id: str, options: List[HITLOption]):
        """Read stdin in background thread so we can be interrupted."""
        def read_input():
            try:
                if options:
                    choices = [opt.label for opt in options]
                    # Use select() or similar to check for cancellation
                    answer = self._interruptible_prompt(choices)
                    if answer is None:  # Cancelled
                        return
                    value = next(opt.value for opt in options if opt.label == answer)
                else:
                    value = self._interruptible_input()
                    if value is None:  # Cancelled
                        return

                # Push response to queue
                self._response_queue.put_nowait(HITLResponse(
                    request_id=request_id,
                    value=value,
                    responded_at=datetime.now(timezone.utc),
                    channel_id=self.channel_id,
                ))
            except Exception as e:
                logger.error(f"CLI input error: {e}")

        self._input_thread = threading.Thread(target=read_input, daemon=True)
        self._input_thread.start()

    def _interruptible_prompt(self, choices: List[str]) -> Optional[str]:
        """Prompt that can be cancelled by _cancel_event."""
        # Implementation uses select() on stdin + a cancel pipe
        # Returns None if cancelled
        ...
```

### ControlLoopHandler - Racing All Channels

```python
class ControlLoopHandler:
    """
    Sends control requests to all enabled channels simultaneously.
    First response wins, others get cancelled.

    Controllers can be humans (HITL) or models (MITL).
    """

    async def request_interaction(
        self,
        procedure_id: str,
        request: HITLRequest,
        context: ExecutionContext,
    ) -> HITLResponse:
        """
        Send to all channels, wait for first response.
        """
        rich_request = self._build_rich_request(request, context)

        # Send to ALL channels (including CLI if terminal is interactive)
        active_channels = []
        for channel in self.channels:
            if channel.channel_id == "cli" and not sys.stdin.isatty():
                continue  # Skip CLI in non-interactive mode

            result = await channel.send(procedure_id, rich_request.request_id, rich_request)
            if result.success:
                active_channels.append(channel)

        if not active_channels:
            raise NoChannelsAvailableError("No notification channels available")

        # Race: wait for first response from any channel
        response = await self._wait_for_first_response(active_channels, rich_request)

        if response:
            # Cancel all other channels
            winning_channel = response.channel_id
            for channel in active_channels:
                if channel.channel_id != winning_channel:
                    await channel.cancel(
                        rich_request.request_id,
                        f"Responded via {winning_channel}"
                    )
            return response

        # No immediate response - save state and exit for resume later
        self.storage.save_hitl_request(procedure_id, rich_request)
        raise ProcedureWaitingForHuman(
            procedure_id=procedure_id,
            request_id=rich_request.request_id,
        )

    async def _wait_for_first_response(
        self,
        channels: List[NotificationChannel],
        request: HITLRequest,
    ) -> Optional[HITLResponse]:
        """
        Wait for first response from any channel.

        For channels like CLI that can respond immediately, this returns quickly.
        For async-only scenarios, this may timeout and return None.
        """
        # Create tasks for each channel's receive() iterator
        receive_tasks = [
            asyncio.create_task(self._get_first_from_channel(ch))
            for ch in channels
        ]

        # Wait for first completion (with timeout for non-blocking channels)
        done, pending = await asyncio.wait(
            receive_tasks,
            timeout=0.1,  # Quick check for immediate responses (like CLI)
            return_when=asyncio.FIRST_COMPLETED,
        )

        # Cancel pending tasks
        for task in pending:
            task.cancel()

        # Return first response if any
        for task in done:
            try:
                response = task.result()
                if response:
                    return response
            except asyncio.CancelledError:
                pass

        return None
```

### Configuration

```yaml
notifications:
  channels:
    cli:
      enabled: ${TACTUS_CLI_HITL:-auto}  # auto, true, false
      # auto = enable if sys.stdin.isatty()
```

### User Experience

**At terminal, respond locally:**
```
Customer Intake: John Doe
Started 2 minutes ago

Input Data:
  name: John Doe
  email: john@example.com

Approve enterprise upgrade?
> [y/n]: y

✓ Approved
```

**At terminal, walk away, respond from phone:**
```
Customer Intake: John Doe
Started 2 minutes ago

Input Data:
  name: John Doe
  email: john@example.com

Approve enterprise upgrade?
> [y/n]: _

✓ Responded via tactus_cloud
```

### Implementation Notes

- Host app **implements** `ControlChannel` protocol (same as remote channels)
- Host app uses **background thread** for local input (interruptible)
- Host app **races** with other channels - no special priority
- **First response wins** regardless of which channel or controller type
- Non-interactive contexts: host channel auto-disabled, other channels still work
- Supports both human controllers (HITL) and model controllers (MITL)

## Channel Lifecycle and Logging

Every channel logs at these points:

| Event | Log Level | Message Format |
|-------|-----------|----------------|
| Init start | INFO | `{channel_id}: initializing...` |
| Init ready | INFO | `{channel_id}: ready` |
| Send | INFO | `{channel_id}: sending notification for {request_id}` |
| Receive | INFO | `{channel_id}: received response for {request_id}` |
| Cancel | DEBUG | `{channel_id}: cancelling {external_message_id}` |
| Shutdown | INFO | `{channel_id}: shutting down` |
| Error | ERROR | `{channel_id}: {error_description}` |

## Tactus Cloud WebSocket API - Detailed Design

### Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                     Tactus Runtime (Agent)                        │
│  TactusCloudChannel connects via WebSocket                        │
│  Sends: Rich HITL requests with full context                     │
│  Receives: Human responses in real-time                           │
└────────────────────┬─────────────────────────────────────────────┘
                     │ WSS + Cognito JWT
                     ↓
┌──────────────────────────────────────────────────────────────────┐
│              AWS API Gateway WebSocket API                        │
│  - Cognito authorizer validates JWT tokens                        │
│  - Routes: $connect, $disconnect, hitl.request, hitl.response    │
│  - Invokes Lambda functions                                       │
└────────────────────┬─────────────────────────────────────────────┘
                     │
        ┌────────────┼────────────┐
        ↓            ↓            ↓
┌─────────────┐ ┌──────────┐ ┌────────────────┐
│  DynamoDB   │ │ Lambda   │ │ Cognito User   │
│ Connections │ │ Handlers │ │ Pool           │
│             │ │          │ │                │
│ Route msgs  │ │ Business │ │ Auth tokens    │
│ by workspace│ │ logic    │ │ User mgmt      │
└─────────────┘ └──────────┘ └────────────────┘
                     │
                     ↓
┌──────────────────────────────────────────────────────────────────┐
│                 Companion App (Human)                             │
│  Mobile/Web connects via WebSocket                                │
│  Receives: HITL requests with rich context                       │
│  Sends: Approval/rejection responses                              │
│  Displays: Conversation history, multi-human collaboration        │
└──────────────────────────────────────────────────────────────────┘
```

### Human Experience (Companion App)

When a human opens the app, they see a list of pending HITL requests:

```
┌─────────────────────────────────────────────────────────┐
│  📋 Pending Requests (3)                                │
├─────────────────────────────────────────────────────────┤
│  🔴 Customer Intake: John Doe                           │
│      Started 2m ago • Waiting on you                    │
│                                                         │
│  🟡 Credit Review: Acme Corp                            │
│      Started 15m ago • Sarah is viewing                 │
│                                                         │
│  🟢 Data Export: Q4 Report                              │
│      Started 1h ago • Approved by Mike                  │
└─────────────────────────────────────────────────────────┘
```

Tapping into a request shows full context:

```
┌─────────────────────────────────────────────────────────┐
│  ← Customer Intake: John Doe                            │
│                                                         │
│  Started: 2 minutes ago                                 │
│  Input: name="John Doe", email="john@example.com"       │
│                                                         │
│  ▼ Conversation History (8 messages)                    │
│  ┌─────────────────────────────────────────────────┐   │
│  │ Agent: Checking customer database...             │   │
│  │ Tool: query_customers(email="john@example.com")  │   │
│  │ Result: Found existing record, 3 support tickets │   │
│  │                                                  │   │
│  │ Agent: Analyzing account history...              │   │
│  │ Tool: get_account_revenue(customer_id=123)       │   │
│  │ Result: $12,000 ARR, payment history: good       │   │
│  │                                                  │   │
│  │ Agent: Customer requested enterprise upgrade.    │   │
│  │ Based on revenue and history, I recommend        │   │
│  │ approval. Should we proceed?                     │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  ▼ Previous Decisions (1)                               │
│  ┌─────────────────────────────────────────────────┐   │
│  │ 1m ago - Sarah: "Verify identity first"          │   │
│  │ Agent: Identity verified via SSO                 │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  Sarah is also viewing this request                     │
│                                                         │
│  ┌─────────┐  ┌─────────┐  ┌──────────────────────┐   │
│  │ Approve │  │ Reject  │  │ Request more info... │   │
│  └─────────┘  └─────────┘  └──────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

### Rich Context Payload

When the agent sends an HITL request, it includes complete context:

```python
{
    "action": "control.request",
    "request_id": "req_abc123",
    "workspace_id": "anthus-qa",
    "namespace": "sales/enterprise-upgrades/manager-approval",

    # Identity
    "procedure": {
        "id": "customer-intake",
        "name": "Customer Intake"
    },
    "invocation": {
        "id": "inv_xyz789",
        "started_at": "2024-01-15T10:30:00Z",
        "elapsed_seconds": 120,
        "subject": "John Doe",
        "input_summary": {
            "name": "John Doe",
            "email": "john@example.com",
            "request_type": "enterprise_upgrade"
        }
    },

    # The question
    "request": {
        "type": "approval",
        "message": "Customer requested enterprise upgrade. Based on revenue and history, I recommend approval. Should we proceed?",
        "options": [
            {"label": "Approve", "value": true, "style": "primary"},
            {"label": "Reject", "value": false, "style": "danger"},
            {"label": "Request more info", "value": "more_info", "style": "secondary"}
        ]
    },

    # Conversation history (full context)
    "conversation": [
        {
            "role": "agent",
            "content": "Checking customer database...",
            "timestamp": "2024-01-15T10:30:05Z"
        },
        {
            "role": "tool",
            "tool_name": "query_customers",
            "tool_input": {"email": "john@example.com"},
            "tool_output": {"found": true, "customer_id": 123, "support_tickets": 3},
            "timestamp": "2024-01-15T10:30:06Z"
        },
        {
            "role": "agent",
            "content": "Found existing record with 3 support tickets",
            "timestamp": "2024-01-15T10:30:07Z"
        },
        // ... more messages
    ],

    # Prior HITL interactions in this invocation
    "prior_hitl": [
        {
            "message": "Should we verify customer identity?",
            "response": "yes",
            "responded_by": "sarah@anthus.ai",
            "responded_at": "2024-01-15T10:31:00Z"
        }
    ]
}
```

### Namespace-Based PubSub Routing with DynamoDB

```python
# DynamoDB Table: tactus-control-connections
# Partition key: connectionId
# GSI: WorkspaceId-Index for workspace isolation

# Agent connection (publisher)
{
    "connectionId": "agent_conn_123",
    "clientType": "agent",
    "workspaceId": "anthus-qa",
    "procedureId": "customer-intake",
    "invocationId": "inv_xyz789",
    "connectedAt": 1234567890,
    "ttl": 1234571490  # Auto-expire after 1 hour
}

# Controller connection (subscriber) with namespace subscriptions
{
    "connectionId": "controller_conn_456",
    "clientType": "controller",
    "userId": "ryan@anthus.ai",
    "workspaceId": "anthus-qa",
    "subscriptions": [
        {"namespace_pattern": "operations/incidents/*", "mode": "respond"},
        {"namespace_pattern": "operations/**", "mode": "observe"}
    ],
    "connectedAt": 1234567890,
    "ttl": 1234575490
}

# Dashboard connection (observer only)
{
    "connectionId": "dashboard_conn_789",
    "clientType": "dashboard",
    "userId": "dashboard-service",
    "workspaceId": "anthus-qa",
    "subscriptions": [
        {"namespace_pattern": "**", "mode": "observe"}  # See everything, respond to nothing
    ],
    "connectedAt": 1234567890,
    "ttl": 1234575490
}

# Query flow for control request:
# 1. Get all connections in workspace: GSI query on WorkspaceId-Index
# 2. Filter by namespace match: pattern match against request.namespace
# 3. Send to all matching subscribers
# 4. Accept responses only from subscribers with mode="respond"
```

**Pattern matching:**
- `*` matches single segment: `operations/*` matches `operations/incidents` but not `operations/incidents/critical`
- `**` matches any depth: `operations/**` matches `operations/incidents/critical/high-priority`

**Response validation:**
```python
def can_respond(subscriber: dict, request_namespace: str) -> bool:
    """Check if subscriber can respond to this namespace."""
    for sub in subscriber['subscriptions']:
        if matches_pattern(sub['namespace_pattern'], request_namespace):
            if sub['mode'] == 'respond':
                return True
    return False
```

### Lambda Handler Examples

```python
# $connect handler
def on_connect(event, context):
    connection_id = event['requestContext']['connectionId']
    claims = event['requestContext']['authorizer']['claims']

    user_id = claims['sub']
    client_type = event['queryStringParameters']['client_type']

    item = {
        'connectionId': connection_id,
        'userId': user_id,
        'clientType': client_type,
        'connectedAt': int(time.time()),
        'ttl': int(time.time()) + 3600
    }

    if client_type == 'agent':
        item['workspaceId'] = event['queryStringParameters']['workspace_id']
    elif client_type == 'human':
        # Get workspaces from Cognito groups
        workspaces = [
            g.replace('workspace:', '')
            for g in claims.get('cognito:groups', [])
            if g.startswith('workspace:')
        ]
        item['workspaces'] = workspaces

    dynamodb.put_item(TableName='tactus-hitl-connections', Item=item)
    return {'statusCode': 200}

# control.request handler (from agent)
def on_control_request(event, context):
    body = json.loads(event['body'])
    workspace_id = body['workspace_id']
    namespace = body.get('namespace', '')

    # Find all subscribers in this workspace
    response = dynamodb.query(
        TableName='tactus-control-connections',
        IndexName='WorkspaceId-Index',
        KeyConditionExpression='workspaceId = :ws',
        ExpressionAttributeValues={':ws': workspace_id}
    )

    # Filter by namespace and send to matching subscribers
    apigw = boto3.client('apigatewaymanagementapi', endpoint_url=CALLBACK_URL)
    for item in response['Items']:
        if item['clientType'] == 'agent':
            continue  # Don't send to other agents

        # Check if any subscription matches the namespace
        subscriptions = item.get('subscriptions', [])
        matching_mode = get_matching_mode(subscriptions, namespace)

        if matching_mode:  # "observe" or "respond"
            try:
                # Include whether they can respond in the payload
                payload = {**body, 'can_respond': matching_mode == 'respond'}
                apigw.post_to_connection(
                    ConnectionId=item['connectionId'],
                    Data=json.dumps(payload)
                )
            except apigw.exceptions.GoneException:
                # Stale connection, clean up
                dynamodb.delete_item(
                    TableName='tactus-control-connections',
                    Key={'connectionId': item['connectionId']}
                )

    return {'statusCode': 200}

def get_matching_mode(subscriptions: list, namespace: str) -> Optional[str]:
    """Return highest privilege mode that matches namespace."""
    matched_mode = None
    for sub in subscriptions:
        if matches_pattern(sub['namespace_pattern'], namespace):
            if sub['mode'] == 'respond':
                return 'respond'  # Highest privilege, return immediately
            matched_mode = 'observe'
    return matched_mode

# control.response handler (from controller)
def on_control_response(event, context):
    connection_id = event['requestContext']['connectionId']
    body = json.loads(event['body'])
    request_id = body['request_id']
    namespace = body.get('namespace', '')

    # Get the subscriber's subscriptions
    subscriber = dynamodb.get_item(
        TableName='tactus-control-connections',
        Key={'connectionId': connection_id}
    ).get('Item')

    if not subscriber:
        return {'statusCode': 403, 'body': 'Connection not found'}

    # Verify they have respond permission for this namespace
    if not can_respond(subscriber, namespace):
        return {'statusCode': 403, 'body': 'Not authorized to respond to this namespace'}

    # Route response to agent (existing logic)
    # ...
```

### CDK Stack Structure

```typescript
// lib/tactus-hitl-api-stack.ts

export class TactusHitlApiStack extends Stack {
  constructor(scope: Construct, id: string) {
    super(scope, id);

    // Cognito User Pool
    const userPool = new cognito.UserPool(this, 'TactusHitlUserPool', {
      signInAliases: { email: true },
      selfSignUpEnabled: false,
      // ... configuration
    });

    // DynamoDB Table
    const connectionsTable = new dynamodb.Table(this, 'Connections', {
      partitionKey: { name: 'connectionId', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      timeToLiveAttribute: 'ttl',
    });

    // Add GSI for workspace routing
    connectionsTable.addGlobalSecondaryIndex({
      indexName: 'WorkspaceId-ClientType-Index',
      partitionKey: { name: 'workspaceId', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'clientType', type: dynamodb.AttributeType.STRING },
    });

    // Lambda handlers
    const connectHandler = new lambda.Function(this, 'ConnectHandler', {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'handlers.on_connect',
      code: lambda.Code.fromAsset('lambda'),
      environment: {
        CONNECTIONS_TABLE: connectionsTable.tableName,
      },
    });

    // ... more handlers

    // API Gateway WebSocket API
    const webSocketApi = new apigatewayv2.WebSocketApi(this, 'HitlWebSocketApi', {
      connectRouteOptions: { integration: new WebSocketLambdaIntegration('ConnectIntegration', connectHandler) },
      disconnectRouteOptions: { integration: new WebSocketLambdaIntegration('DisconnectIntegration', disconnectHandler) },
    });

    webSocketApi.addRoute('hitl.request', {
      integration: new WebSocketLambdaIntegration('RequestIntegration', requestHandler),
    });

    webSocketApi.addRoute('hitl.response', {
      integration: new WebSocketLambdaIntegration('ResponseIntegration', responseHandler),
    });

    // Authorizer
    const authorizer = new apigatewayv2.WebSocketAuthorizer(this, 'CognitoAuthorizer', {
      webSocketApi,
      identitySource: ['route.request.querystring.token'],
      type: apigatewayv2.WebSocketAuthorizerType.CUSTOM,
      authorizerHandler: authorizerHandler,
    });

    // Deploy
    new apigatewayv2.WebSocketStage(this, 'ProdStage', {
      webSocketApi,
      stageName: 'prod',
      autoDeploy: true,
    });
  }
}
```

### Deployment

```bash
# Deploy the CDK stack
cd infrastructure/tactus-hitl-api
cdk deploy

# Outputs:
# WebSocketUrl: wss://abc123.execute-api.us-east-1.amazonaws.com/prod
# UserPoolId: us-east-1_abc123
# UserPoolClientId: 1234567890abcdef
```

Configure Tactus:

```yaml
# ~/.tactus/config.yml
notifications:
  channels:
    tactus_cloud:
      enabled: true
      api_url: wss://abc123.execute-api.us-east-1.amazonaws.com/prod
      token: ${TACTUS_CLOUD_TOKEN}
      workspace_id: anthus-qa
```

## Channel Examples

### SQS Channel (In-Process, Polling)

```python
class SQSNotificationChannel(InProcessChannel):
    """
    AWS SQS channel - demonstrates polling-based in-process channel.

    - Sends: POST message to SQS queue
    - Receives: Polls queue in background asyncio task
    """

    async def initialize(self) -> None:
        logger.info(f"{self.channel_id}: initializing...")
        self._sqs_client = await self._create_sqs_client()
        self._poll_task = asyncio.create_task(self._poll_loop())
        logger.info(f"{self.channel_id}: ready")

    async def send(self, ...) -> NotificationDeliveryResult:
        logger.info(f"{self.channel_id}: sending notification for {request_id}")
        await self._sqs_client.send_message(...)
        return NotificationDeliveryResult(...)

    async def receive(self) -> AsyncIterator[HITLResponse]:
        while True:
            response = await self._response_queue.get()
            logger.info(f"{self.channel_id}: received response for {response.request_id}")
            yield response

    async def _poll_loop(self) -> None:
        """Background task polling SQS for responses."""
        while True:
            messages = await self._sqs_client.receive_messages(...)
            for msg in messages:
                await self._response_queue.put(self._parse_response(msg))
            await asyncio.sleep(1)
```

### Slack Channel (In-Process, Webhook)

```python
class SlackNotificationChannel(InProcessChannel):
    """
    Slack channel - demonstrates webhook-based in-process channel.

    - Sends: POST to Slack API with Block Kit message
    - Receives: Webhook handler pushes to internal queue
    """

    async def send(self, ...) -> NotificationDeliveryResult:
        logger.info(f"{self.channel_id}: sending notification for {request_id}")
        # POST to Slack API with interactive buttons
        # Buttons include callback data for response routing
        ...

    def handle_interactivity_webhook(self, payload: dict) -> None:
        """
        Called by deployer's webhook endpoint.

        Example FastAPI integration:
            @app.post("/slack/interactivity")
            async def slack_webhook(request: Request):
                slack_channel.handle_interactivity_webhook(await request.json())
        """
        response = self._parse_slack_action(payload)
        self._response_queue.put_nowait(response)
```

## Current State

**Nothing is in production** - we have a clean slate with no backward compatibility concerns.

Existing placeholder implementations can be deleted and replaced entirely. The architecture described in this document is the target state.

## Implementation Phases

### Phase 1: Tactus Cloud WebSocket API (HIGHEST PRIORITY)

**Why this is the ideal first channel:**
- ✅ Complete control over both client and server
- ✅ No third-party app registration or API documentation learning curve
- ✅ AI agents can iterate autonomously on both sides
- ✅ Event-driven with low latency (WebSocket)
- ✅ Simple, serverless architecture (API Gateway + Cognito + DynamoDB)
- ✅ Deployed via CDK (our standard IaC tool)
- ✅ Perfect for companion app integration

**Components:**

1. **CDK Stack** (`tactus-hitl-api-stack`)
   - API Gateway WebSocket API
   - Cognito User Pool (token-based auth)
   - DynamoDB table for connection routing
   - Lambda handlers ($connect, $disconnect, hitl.request, hitl.response)
   - IAM roles and policies

2. **Tactus Channel** (`tactus/adapters/channels/tactus_cloud.py`)
   - InProcessChannel implementation
   - WebSocket client with Cognito auth
   - Rich payload construction (context, conversation, history)
   - Real-time response handling

3. **Protocol Extensions** (to support rich context)
   - Extend HITLRequest with: procedure_name, invocation_id, subject, input_summary, conversation, prior_hitl
   - Runtime context gathering in ExecutionContext
   - ConversationMessage and HITLInteraction models

4. **Configuration**
   ```yaml
   notifications:
     channels:
       tactus_cloud:
         enabled: true
         api_url: wss://hitl.tactus.cloud
         token: ${TACTUS_CLOUD_TOKEN}
         workspace_id: ${TACTUS_WORKSPACE_ID}
   ```

### Phase 2: Core Protocol Revision

1. Update `tactus/protocols/notification.py` with revised protocol
2. Create `InProcessChannel` base class
3. Create `ChannelManager` for lifecycle management
4. Add standardized logging
5. Extend models for rich context (conversation, history)

### Phase 3: Additional Self-Hosted Channels

Based on actual requirements:
- Teams (webhook, similar to Slack)
- Email (SMTP send, fire-and-forget)
- SQS (polling, demonstrates async pattern)
- Slack (webhook-based)

### Phase 4: Daemon Architecture (Future)

If needed for heavy channels like Discord:
- Design daemon protocol (based on existing `tactus/broker/`)
- Implement `DaemonChannel` base class
- Create Discord daemon implementation

## Configuration

```yaml
# ~/.tactus/config.yml
notifications:
  enabled: true

  channels:
    slack:
      enabled: true
      token: ${SLACK_BOT_TOKEN}
      default_channel: "#tactus-alerts"

    sqs:
      enabled: true
      queue_url: ${SQS_QUEUE_URL}
      response_queue_url: ${SQS_RESPONSE_QUEUE_URL}

    email:
      enabled: false
      smtp_host: "smtp.example.com"
      smtp_port: 587
      from_address: "tactus@example.com"
      recipients: ["ops@example.com"]
```

## Open Questions

1. **Response coordination**: How exactly does first-wins work with concurrent responses?
2. **Channel priorities**: Should some channels be "primary" vs "fallback"?
3. **Timeout handling**: What happens if no response within timeout?
4. **Cloud backbone**: Deferred - focus on self-hosted channels first
5. **Namespace specification**: How does procedure author specify namespace for control requests?
   - Option A: Explicit in Lua call: `Human.approve("OK?", {namespace = "ops/incidents/level3"})`
   - Option B: Procedure-level config in front matter
   - Option C: Runtime config that applies to all control requests from that procedure
6. **Namespace pattern matching**: What glob/wildcard syntax for subscriptions?
   - `*` matches single segment, `**` matches any depth (like gitignore)
   - Or use regex patterns?
7. **Subscription management**: How do controllers subscribe to namespaces?
   - At connection time via query params?
   - Via separate WebSocket message after connecting?
   - Via Cognito groups (workspace-level only)?

## Notes

- All channel implementations are currently placeholders/examples
- Focus on in-process channels first (YAGNI on daemon complexity)
- Daemon architecture documented for future reference if needed
- Exit-and-resume pattern integrates cleanly with existing Tactus runtime
- Broker protocol at `tactus/broker/` provides reference for future daemon IPC

---

## Phase 4.1: Complete Registry Migration - Implementation Plan

### Goal
Eliminate the last remaining hard-coded rendering in modal mode and achieve 100% unified component architecture.

### Current State
- ✅ Registry infrastructure exists ([tactus-ide/frontend/src/components/hitl/registry.ts](../tactus-ide/frontend/src/components/hitl/registry.ts))
- ✅ Built-in components extracted (ApprovalComponent, InputComponent, SelectComponent)
- ✅ Inline mode uses registry via `renderFormItem()` helper
- ❌ Modal mode has 63 lines of hard-coded rendering (lines 332-399)

### The Problem
File: [tactus-ide/frontend/src/components/events/HITLEventComponent.tsx](../tactus-ide/frontend/src/components/events/HITLEventComponent.tsx)

**Lines 332-399:** Modal TabsContent has hard-coded conditionals:
```typescript
{item.request_type === 'approval' && (
  /* 20 lines of approval buttons */
)}
{item.request_type === 'input' && (
  /* 8 lines of input field */
)}
{item.request_type === 'select' && (
  /* 35 lines of select buttons */
)}
```

This creates:
1. **Code duplication** - Same logic exists in inline mode
2. **Inconsistent behavior** - Changes need to be made twice
3. **Limited extensibility** - Custom components can't be used in modal mode

### The Fix
Replace hard-coded conditionals with `renderFormItem()` helper (same as inline mode):

```typescript
// BEFORE (lines 324-400) - 77 lines total
<TabsContent key={item.item_id} value={item.item_id} className="space-y-4">
  <div>
    <Label className="text-base font-semibold">{item.message}</Label>
    {item.required && <span className="text-destructive ml-1">*</span>}
  </div>

  {/* Render input based on type */}
  {item.request_type === 'approval' && (
    <div className="space-y-2">
      <Button onClick={...}>Approve</Button>
      <Button onClick={...}>Reject</Button>
    </div>
  )}

  {item.request_type === 'input' && (
    <input type="text" onChange={...} />
  )}

  {item.request_type === 'select' && (
    <div className="grid grid-cols-2 gap-2">
      {item.options.map(option => (
        <Button onClick={...}>{option.label}</Button>
      ))}
    </div>
  )}
</TabsContent>

// AFTER - 14 lines (63 lines removed!)
<TabsContent key={item.item_id} value={item.item_id} className="space-y-4">
  <div>
    <Label className="text-base font-semibold">{item.message}</Label>
    {item.required && <span className="text-destructive ml-1">*</span>}
  </div>

  {renderFormItem(item)}
</TabsContent>
```

### Benefits
1. ✅ **Eliminates 63 lines** of duplicate code
2. ✅ **Unified rendering** - Modal and inline use identical logic
3. ✅ **Custom components work in modal** - ImageSelector, etc. will render
4. ✅ **Single source of truth** - Changes happen once, apply everywhere
5. ✅ **Easier maintenance** - One component to update, not two
6. ✅ **Fully extensible** - Applications can override any component type

### Verification Steps
1. **Switch config** to `batched_inputs_mode: modal`
2. **Run test** - `tactus run examples/92-test-inputs.tac`
3. **Verify all types** render correctly in modal:
   - Approval buttons (Approve/Reject)
   - Input fields (text, placeholder)
   - Select buttons (single-select and multi-select)
4. **Test custom components** in modal (future test with ImageSelectorComponent)
5. **Visual regression** - Modal should look identical to before

### Files Modified
- [tactus-ide/frontend/src/components/events/HITLEventComponent.tsx](../tactus-ide/frontend/src/components/events/HITLEventComponent.tsx) - Lines 332-399

### Success Criteria
- [ ] Modal mode uses `renderFormItem()` instead of hard-coded conditionals
- [ ] All input types render correctly in modal (approval, input, select)
- [ ] Multi-select shows visual feedback (check marks, selected state)
- [ ] Form validation works (required fields, Submit All button state)
- [ ] Custom components render in modal (ImageSelectorComponent test)
- [ ] No visual regressions (modal looks identical to before)
- [ ] Frontend builds without errors
- [ ] Test example passes in modal mode

---

## Phase 5: Comprehensive Testing Plan

### Testing Goals

Thoroughly test all HITL request types across execution modes (direct and container) to ensure:
1. All control request types work correctly
2. Multi-channel racing behaves properly
3. Timeout and default values are handled
4. Checkpoint/resume works across HITL waits
5. Real-time streaming works for all event types
6. Edge cases are handled gracefully

### HITL Request Types to Test

| Request Type | Method | Purpose | Required Fields |
|-------------|---------|---------|-----------------|
| **approval** | `Human.approve(message)` | Binary yes/no decision | `message` |
| **input** | `Human.input(message, [default])` | Text input collection | `message`, optional `default_value` |
| **select** | `Human.select(message, options)` | Single choice from list | `message`, `options` array |
| **inputs** | `Human.inputs({field1, field2, ...})` | Batched multi-field form | Array of input definitions |
| **review** | `Human.review(content, [context])` | Document/data review | `content`, optional `context` |
| **escalation** | `Human.escalate(reason, [severity])` | Exception handling | `reason`, optional `severity` |

### Test Matrix

For each request type, test the following scenarios:

#### Execution Modes
- [ ] Direct execution (no container)
- [ ] Container execution with broker

#### Channels
- [ ] CLI only (ControlLoopHandler with CLIControlChannel)
- [ ] IDE only (ControlLoopHandler with SSEControlChannel)
- [ ] Both channels (multi-channel racing - first to respond wins)

#### Response Scenarios
- [ ] Normal response (user provides valid input)
- [ ] Timeout (no response within timeout period)
- [ ] Default value (when provided and timeout occurs)
- [ ] Invalid input (validation errors)
- [ ] Channel failure (channel send fails)

#### Event Streaming
- [ ] HITL request appears in IDE
- [ ] Agent responses stream in real-time
- [ ] Log events appear during execution
- [ ] Procedure completion shows final result

### Test Examples to Create

#### 1. Human.approve() - Binary Decision
File: `examples/93-test-approve.tac`
- Ask for deployment approval
- Branch on result (approved vs rejected)
- Test with timeout and default value

#### 2. Human.input() - Text Collection
File: `examples/94-test-input.tac`
- Collect user's name
- Collect configuration value with default
- Use input in subsequent logic

#### 3. Human.select() - Single Choice
File: `examples/95-test-select.tac`
- Choose deployment environment (dev/staging/prod)
- Choose log level (debug/info/warn/error)
- Use selection to configure behavior

#### 4. Human.inputs() - Batched Form
File: `examples/96-test-inputs.tac`
- Multi-field form (name, email, role, preferences)
- Mix of text inputs, selects, and checkboxes
- Validate form-wide constraints

#### 5. Human.review() - Document Review
File: `examples/97-test-review.tac`
- Review generated code
- Review configuration changes
- Approve/reject with feedback

#### 6. Human.escalate() - Exception Handling
File: `examples/98-test-escalate.tac`
- Detect error condition
- Escalate to on-call
- Wait for resolution or timeout

#### 7. Multi-Channel Racing
File: `examples/99-test-racing.tac`
- Send HITL request to both CLI and IDE
- Verify first response wins
- Verify other channels are cancelled

#### 8. Timeout Behavior
File: `examples/100-test-timeout.tac`
- Request with short timeout (5 seconds)
- Request with default value on timeout
- Request without default (should fail on timeout)

### Testing Checklist

#### Basic Functionality
- [ ] Remove emojis from examples (no emojis in code)
- [ ] Human.approve() works in containers
- [ ] Human.approve() works in direct execution
- [ ] IDE displays approval UI correctly
- [ ] CLI displays approval prompt correctly
- [ ] Agent responses stream in real-time
- [ ] Log events appear during execution
- [ ] Final result displays in IDE

#### All Request Types
- [ ] Human.input() collects text
- [ ] Human.select() shows options
- [ ] Human.inputs() renders multi-field form
- [ ] Human.review() displays content
- [ ] Human.escalate() triggers notification

#### Channel Behavior
- [ ] SSEControlChannel delivers to IDE
- [ ] CLIControlChannel delivers to terminal
- [ ] Both channels race properly
- [ ] Winner's response is used
- [ ] Loser's channel is cancelled

#### Error Handling
- [ ] Timeout triggers default value if provided
- [ ] Timeout fails gracefully if no default
- [ ] Invalid responses are rejected
- [ ] Channel failures don't crash procedure
- [ ] Network issues are handled

#### Event Streaming
- [ ] AgentTurnEvent chunks stream in real-time
- [ ] LogEvents appear as they're emitted
- [ ] CostEvents are tracked
- [ ] ExecutionSummaryEvent shows final result
- [ ] Container events flow through broker correctly

#### Container-Specific
- [ ] BrokerControlChannel bridges to host
- [ ] BrokerLogHandler streams events
- [ ] Background thread worker doesn't block
- [ ] Flush ensures all events delivered
- [ ] LLM backend config passed correctly

### Success Criteria

Phase 4 testing is complete when:
1. All HITL request types work in both execution modes
2. Multi-channel racing behaves correctly
3. Timeout behavior is predictable and documented
4. All events stream in real-time without blocking
5. Edge cases are handled gracefully
6. Test examples demonstrate each feature
7. No emojis in code or examples

### Next Steps After Testing

1. Document any issues found during testing
2. Fix any bugs discovered
3. Create comprehensive test examples
4. Update user documentation
5. Consider Phase 5: External channels (Slack, Discord, etc.)

---

## Phase 5: HITL Context Architecture

### Problem Statement

When HITL requests are displayed in a unified inbox or notification center (out-of-context), humans need rich context to understand what they're being asked and why. Procedure inputs alone are insufficient:

1. **Procedure inputs** = what the procedure needs to do its job
2. **Context** = what humans need to understand *why* this is happening and trace back to the source

### Two Layers of Context

#### 1. Runtime Context (Tactus-Provided, Automatic)

Information the Tactus runtime automatically captures regardless of how the procedure is invoked:

| Field | Description | Universality |
|-------|-------------|--------------|
| `source_line` | Line number where HITL request originated | Universal - code always has structure |
| `source_file` | File path (if code stored as file) | Optional - depends on storage format |
| `checkpoint_position` | Position in execution log | Universal |
| `procedure_name` | Name of the running procedure | Universal |
| `invocation_id` | Unique identifier for this execution | Universal |
| `started_at` | When execution began | Universal |
| `elapsed_seconds` | Time since execution started | Universal |
| `backtrace` | Execution path to reach this point | Universal (from checkpoint log) |

**Key insight:** Line number is more universal than file name. The code exists in some form (string, file, database record) and always has line structure, even if the storage mechanism varies.

#### 2. Application Context (Host-Provided, Manual)

Domain-specific context that only the embedding application knows:

```typescript
interface ContextLink {
  name: string;      // Display label (e.g., "Evaluation", "Customer")
  value: string;     // Display value (e.g., "Monthly QA Review")
  url?: string;      // Optional deep link to the source in the host application
}
```

**Examples:**
```typescript
[
  { name: "Evaluation", value: "Monthly QA Review", url: "/evaluations/123" },
  { name: "Scorecard", value: "Customer Support Quality", url: "/scorecards/456" },
  { name: "Agent", value: "Support Triage Bot", url: "/agents/789" },
  { name: "Customer", value: "Acme Corp", url: "/customers/acme" }
]
```

**Why this matters:** When you have multiple agents running independently, each generating HITL requests, a unified inbox needs to show where each request came from. The procedure doesn't need to know it's running as part of "Evaluation 123" to do its job, but the human operator absolutely needs this context to make informed decisions.

### Display Modes: In-Context vs Out-of-Context

HITL components support two display modes:

#### In-Context Mode (`displayMode: 'inline'`)
- Component is displayed within the procedure's execution stream
- **Shows** runtime context (source line, elapsed time, checkpoint position)
- **Hides** application context (domain-specific links only make sense in unified inbox)
- Runtime context is useful even when surrounded by logs

#### Out-of-Context Mode (`displayMode: 'standalone'`)
- Component is displayed in a unified inbox, notification center, or external app
- User has no surrounding context
- **Shows** both runtime context and application context
- Context displayed **above** the question (establishes "what is this about?" before "what are you being asked?")

### Protocol Types

#### Python Backend ([tactus/protocols/control.py](../tactus/protocols/control.py))

```python
@dataclass
class BacktraceEntry:
    """Single entry in the execution backtrace."""
    checkpoint_type: str
    line: Optional[int] = None
    function_name: Optional[str] = None
    duration_ms: Optional[float] = None

@dataclass
class RuntimeContext:
    """Context automatically captured from the Tactus runtime."""
    source_line: Optional[int] = None
    source_file: Optional[str] = None
    checkpoint_position: int = 0
    procedure_name: str = ""
    invocation_id: str = ""
    started_at: Optional[datetime] = None
    elapsed_seconds: float = 0.0
    backtrace: List[BacktraceEntry] = field(default_factory=list)

@dataclass
class ContextLink:
    """Application-provided context reference."""
    name: str
    value: str
    url: Optional[str] = None
```

#### TypeScript Frontend ([tactus-ide/frontend/src/types/events.ts](../tactus-ide/frontend/src/types/events.ts))

```typescript
interface BacktraceEntry {
  checkpoint_type: string;
  line?: number;
  function_name?: string;
  duration_ms?: number;
}

interface RuntimeContext {
  source_line?: number;
  source_file?: string;
  checkpoint_position: number;
  procedure_name: string;
  invocation_id: string;
  started_at?: string;
  elapsed_seconds: number;
  backtrace: BacktraceEntry[];
}

interface ContextLink {
  name: string;
  value: string;
  url?: string;
}
```

### Frontend Component Layout (Standalone Mode)

```
+-------------------------------------------------------------------+
| Awaiting Human Input                          procedure_name      |
+-------------------------------------------------------------------+
|                                                                   |
| +--- Context (standalone mode only) ----------------------------+ |
| |  Line 42 in examples/93-test.tac                              | |
| |  Running for 2m 30s (checkpoint 5)                            | |
| |                                                                | |
| |  Evaluation: Monthly QA Review        [link]                   | |
| |  Scorecard: Customer Support Quality  [link]                   | |
| |  Customer: Acme Corp                  [link]                   | |
| +----------------------------------------------------------------+ |
|                                                                   |
| +--- Question ----------------------------------------------------+ |
| |  Deploy v1.0.0 to production?                                   | |
| |                                                                  | |
| |  [Reject]  [Approve]                                             | |
| +------------------------------------------------------------------+ |
+-------------------------------------------------------------------+
```

### Implementation Files

**Backend (Python):**
- [tactus/protocols/control.py](../tactus/protocols/control.py) - Protocol types
- [tactus/core/execution_context.py](../tactus/core/execution_context.py) - `get_runtime_context()`, `get_lua_source_line()`
- [tactus/adapters/control_loop.py](../tactus/adapters/control_loop.py) - Context passing
- [tactus/adapters/channels/sse.py](../tactus/adapters/channels/sse.py) - SSE serialization

**Frontend (TypeScript/React):**
- [tactus-ide/frontend/src/types/events.ts](../tactus-ide/frontend/src/types/events.ts) - Type definitions
- [tactus-ide/frontend/src/components/events/HITLEventComponent.tsx](../tactus-ide/frontend/src/components/events/HITLEventComponent.tsx) - Display component
- [tactus-ide/frontend/src/components/events/HITLEventComponent.stories.tsx](../tactus-ide/frontend/src/components/events/HITLEventComponent.stories.tsx) - Storybook stories

### Use Cases

| Scenario | Display Mode | Context Shown |
|----------|--------------|---------------|
| IDE Event Stream | `inline` | Runtime context (source line, elapsed time) |
| Unified Inbox | `standalone` | Runtime context + application context |
| Mobile Notification | `standalone` | Runtime context + application context |
| Slack/Discord Integration | `standalone` | Runtime context + application context |

### Setting Application Context

Host applications set context when invoking procedures:

```python
# Option 1: At procedure invocation time
result = await runtime.execute(
    source=procedure_source,
    context={
        "user_id": user_id,
        # ... other inputs
    },
    application_context=[
        {"name": "Evaluation", "value": "Monthly QA", "url": "/evals/123"},
        {"name": "Scorecard", "value": "Support Quality", "url": "/scorecards/456"},
    ]
)
```

### Success Criteria

- [x] RuntimeContext captured automatically by runtime
- [x] RuntimeContext and ContextLink types in protocol
- [x] HITLEventComponent supports `displayMode` prop
- [x] Inline mode hides context (current default behavior)
- [x] Standalone mode shows context above question
- [x] Context links are clickable
- [x] Storybook stories document both modes
- [ ] Application context can be passed at invocation time (future enhancement)
