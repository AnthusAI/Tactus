# Phase 3: IDE/SSE HITL Integration - Complete

**Status:** ✅ Frontend integration complete and ready for testing
**Date:** 2026-01-19

## Summary

Successfully integrated the omnichannel HITL system with the Tactus Web IDE frontend. The IDE can now receive HITL requests via Server-Sent Events (SSE) and display interactive prompts inline in the execution results.

---

## What Was Implemented

### 1. HITL Event Types ([tactus-ide/frontend/src/types/events.ts](tactus-ide/frontend/src/types/events.ts))

Added comprehensive TypeScript types for HITL events:

- `HITLRequestType` - Union type for all request types (approval, input, select, etc.)
- `HITLOption` - Option buttons with labels, values, and styles
- `HITLRequestItem` - Individual items in batched inputs
- `ConversationMessage` - Agent conversation history
- `ControlInteraction` - Prior HITL interactions
- `HITLRequestEvent` - Main event sent via SSE stream
- `HITLCancelEvent` - Cancellation notifications

Added to the `AnyEvent` union for proper type safety throughout the IDE.

### 2. HITL Event Component ([tactus-ide/frontend/src/components/events/HITLEventComponent.tsx](tactus-ide/frontend/src/components/events/HITLEventComponent.tsx))

Created a new React component to display HITL requests inline in the event stream:

**Features:**
- Bell icon for pending requests, checkmark for responded
- Displays procedure name, subject, and message
- Renders appropriate UI based on request type:
  - **Approval**: Buttons with primary/danger styling
  - **Input**: Text input with submit button
  - **Select**: Option buttons
  - **Inputs**: Batched form (simplified inline view)
- Shows rich context indicators (input summary, conversation, prior interactions)
- Handles response submission via callback
- Updates UI to show confirmed response

### 3. Event Renderer Integration ([tactus-ide/frontend/src/components/events/EventRenderer.tsx](tactus-ide/frontend/src/components/events/EventRenderer.tsx))

Updated EventRenderer to handle HITL events:

- Added `onHITLRespond` callback prop
- Route `hitl.request` events to HITLEventComponent
- Handle `hitl.cancel` events (display cancellation notice)

### 4. Message Feed Updates ([tactus-ide/frontend/src/components/MessageFeed.tsx](tactus-ide/frontend/src/components/MessageFeed.tsx))

Added HITL response callback support:

- Added `onHITLRespond` prop to MessageFeedProps
- Passed callback through to EventRenderer

### 5. CollapsibleRun Updates ([tactus-ide/frontend/src/components/CollapsibleRun.tsx](tactus-ide/frontend/src/components/CollapsibleRun.tsx))

Extended run display to support HITL:

- Added `onHITLRespond` prop
- Passed through to MessageFeed

### 6. Results Sidebar Updates ([tactus-ide/frontend/src/components/ResultsSidebar.tsx](tactus-ide/frontend/src/components/ResultsSidebar.tsx))

Extended sidebar props:

- Added `onHITLRespond` callback prop
- Passed through to CollapsibleRun

### 7. App.tsx Integration ([tactus-ide/frontend/src/App.tsx](tactus-ide/frontend/src/App.tsx))

Created HITL response handler and wired it up:

```typescript
const handleHITLRespond = useCallback(async (requestId: string, value: any) => {
  try {
    const url = apiUrl(`/api/hitl/response/${requestId}`);
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ value }),
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    console.log(`HITL response sent for ${requestId}:`, value);
  } catch (error) {
    console.error('Error sending HITL response:', error);
    alert('Failed to send response. Please try again.');
  }
}, []);
```

Passed handler to ResultsSidebar component.

---

## Architecture Flow

```
User runs procedure in IDE
    ↓
Backend SSEControlChannel emits hitl.request event
    ↓
IDE's useEventStream hook receives event via SSE
    ↓
Event flows through MessageFeed → EventRenderer → HITLEventComponent
    ↓
User clicks button/submits input
    ↓
HITLEventComponent calls onHITLRespond callback
    ↓
App.tsx handleHITLRespond posts to /api/hitl/response/<request_id>
    ↓
Flask endpoint calls SSEControlChannel.handle_ide_response()
    ↓
Response queued in channel's _response_queue
    ↓
ControlLoopHandler.receive() yields response
    ↓
Procedure resumes with user's response
```

---

## Testing Checklist

### Prerequisites
1. ✅ Backend SSE channel implemented ([tactus/adapters/channels/sse.py](tactus/adapters/channels/sse.py))
2. ✅ Flask endpoints configured ([tactus/ide/server.py](tactus/ide/server.py))
3. ✅ SSE channel wired into IDE runtime (lines 750-768 in server.py)
4. ✅ Frontend types and components implemented

### Test Procedure

**1. Start the Tactus IDE:**
```bash
cd tactus-ide
npm run dev  # Or your IDE start command
```

**2. Create a test procedure:**
```lua
-- examples/test-ide-hitl.tac
procedure TestIDEHITL() {
    print("Starting HITL test")

    -- Test approval
    local approved = Human.approval(
        "Should we proceed with the test?",
        {
            {label = "Yes", value = true, style = "primary"},
            {label = "No", value = false, style = "danger"}
        }
    )

    print("User approved: " .. tostring(approved))

    -- Test input
    local name = Human.input("What is your name?")
    print("User name: " .. name)

    -- Test select
    local color = Human.select(
        "What is your favorite color?",
        {
            {label = "Red", value = "red"},
            {label = "Blue", value = "blue"},
            {label = "Green", value = "green"}
        }
    )

    print("User color: " .. color)
}
```

**3. Run the procedure in IDE:**
- Open `examples/test-ide-hitl.tac` in the IDE
- Click the "Run" button
- **Expected:** Procedure executes and hits first HITL checkpoint

**4. Verify HITL UI appears:**
- **Expected:** Bell icon with "Awaiting Human Input" in the results panel
- **Expected:** "Should we proceed with the test?" message displayed
- **Expected:** Two buttons: "Yes" (primary) and "No" (danger)

**5. Click "Yes" button:**
- **Expected:** Button click sends POST to `/api/hitl/response/<request_id>`
- **Expected:** UI updates to show green checkmark and "Response Sent"
- **Expected:** Procedure resumes execution

**6. Verify input prompt:**
- **Expected:** Text input field with "What is your name?" message
- **Expected:** Type name and press Enter or click Submit
- **Expected:** Response sent, procedure resumes

**7. Verify select prompt:**
- **Expected:** Three option buttons for colors
- **Expected:** Click one, response sent, procedure completes

**8. Check console logs:**
- Look for: `HITL response sent for <request_id>: <value>`
- Look for: SSE connection logs in browser console

**9. Test multi-channel racing:**
```bash
# In a separate terminal, run with CLI
cd /Users/ryan.porter/Projects/Tactus_4
tactus run examples/test-ide-hitl.tac
```
- **Expected:** Both CLI and IDE receive the HITL request
- **Expected:** First response wins (either CLI or IDE)
- **Expected:** Other channel's UI updates to show request was answered

---

## Known Limitations

1. **Batched inputs (`Human.inputs()`)** - Currently shows a simplified inline view with "Open Form" button (not yet implemented). The full `HITLInputsPanel` from `@anthus/tactus-hitl-components` needs modal integration.

2. **Review, Upload, Escalation** - These request types show a fallback message. Full UI components exist in `@anthus/tactus-hitl-components` but need to be imported and wired up.

3. **Rich context display** - Conversation history and prior interactions are indicated with emojis but not rendered in full detail. A collapsible context panel could be added.

4. **Timeout handling** - No visual countdown timer for requests with `timeout_seconds`. The backend will timeout automatically, but UI could show remaining time.

---

## Next Steps

### Immediate Testing
1. Test basic approval flow end-to-end
2. Test input and select flows
3. Verify multi-channel racing (CLI + IDE)
4. Test procedure resume after response

### Future Enhancements
1. **Import full HITL components** - Use `@anthus/tactus-hitl-components` for richer UI
   - `HITLRequestRenderer` for full feature support
   - Modal for batched inputs
   - Review, upload, escalation panels

2. **Rich context panel** - Expand conversation history and prior interactions

3. **Timeout indicators** - Visual countdown for timed requests

4. **Response history** - Show which channel responded in multi-channel scenarios

5. **Notification system** - Browser notifications for HITL requests when IDE is in background

---

## Success Criteria

- ✅ HITL events flow from backend to IDE via SSE
- ✅ UI renders appropriate controls based on request type
- ⏳ User can respond to HITL requests inline
- ⏳ Responses POST to backend correctly
- ⏳ Procedures resume with user responses
- ⏳ Multi-channel racing works (CLI + IDE)

---

## Files Modified

### Backend (No Changes - Already Complete)
- `tactus/adapters/channels/sse.py` - SSE channel implementation
- `tactus/ide/server.py` - Flask endpoints

### Frontend (New/Modified)
- `tactus-ide/frontend/src/types/events.ts` - Added HITL event types
- `tactus-ide/frontend/src/components/events/HITLEventComponent.tsx` - **NEW** component
- `tactus-ide/frontend/src/components/events/EventRenderer.tsx` - Added HITL routing
- `tactus-ide/frontend/src/components/MessageFeed.tsx` - Added callback prop
- `tactus-ide/frontend/src/components/CollapsibleRun.tsx` - Added callback prop
- `tactus-ide/frontend/src/components/ResultsSidebar.tsx` - Added callback prop
- `tactus-ide/frontend/src/App.tsx` - Added response handler

---

## Phase 3 Status: READY FOR TESTING

The frontend integration is complete. All code is in place to receive HITL events via SSE and send responses via HTTP POST. The next step is end-to-end testing with a running procedure.
