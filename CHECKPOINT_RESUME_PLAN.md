# Checkpoint and Resume Implementation Plan

## Problem Statement

Currently, when a procedure hits `Human.approve()` or other HITL calls:
1. ✅ It raises `ProcedureWaitingForHuman`
2. ✅ The pending request is stored in storage backend
3. ❌ **ON RESUME: The runtime doesn't check for existing responses**
4. ❌ **The procedure reruns from scratch, not from checkpoint**

**Required behavior:**
- Kill a procedure waiting for human input (Ctrl+C)
- Restart the procedure
- It should resume from the exact checkpoint where it was waiting
- LLM calls should return the same cached results
- Human responses should be retrieved from storage if available

## Current State

### What Works ✅
- `ControlLoopHandler._store_pending()` - Stores pending HITL request
- `ControlLoopHandler.check_pending_response()` - Can retrieve stored responses
- `ProcedureWaitingForHuman` exception raised and caught
- Storage backend supports `get_state()` and `set_state()`

### What's Missing ❌

1. **Resume Flow Not Implemented**
   - Runtime doesn't check `check_pending_response()` on restart
   - No logic to skip to the checkpoint position
   - No integration with execution log checkpoints

2. **LLM Completion Caching**
   - No caching of LLM responses for deterministic replay
   - Need to store completions in execution log
   - Need to replay from cache on resume

3. **Checkpoint Position Tracking**
   - Need to know which checkpoint we're resuming from
   - Need to skip already-executed steps
   - Need to restore Lua execution state

## Implementation Steps

### Phase 1: Basic Resume Flow

**Goal:** Kill and restart a procedure waiting for HITL, have it check storage for response and continue.

**Files to Modify:**

1. **`tactus/core/runtime.py`** - Add resume check at start of execution:
```python
async def execute(self, ...):
    # ... existing setup ...

    # Check for pending HITL responses BEFORE executing workflow
    if self.control_handler and self.storage:
        pending_responses = await self._check_pending_control_responses(procedure_id)
        if pending_responses:
            logger.info(f"Found {len(pending_responses)} pending control responses, resuming...")
            # Store these for the control loop to return immediately
            self._pending_responses = pending_responses

    # ... continue with normal execution ...

async def _check_pending_control_responses(self, procedure_id: str):
    """Check storage for any pending control responses."""
    state = self.storage.get_state(procedure_id) or {}
    responses = {}
    for key, value in state.items():
        if key.startswith("control_pending:"):
            if value.get("response"):
                request_id = key.replace("control_pending:", "")
                responses[request_id] = ControlResponse(**value["response"])
    return responses
```

2. **`tactus/adapters/control_loop.py`** - Check for cached responses first:
```python
async def _request_interaction_async(self, request: ControlRequest) -> ControlResponse:
    # Check if we already have a response from previous run
    if self.storage:
        cached_response = self.check_pending_response(
            request.procedure_id,
            request.request_id
        )
        if cached_response:
            logger.info(f"Using cached response for {request.request_id}")
            return cached_response

    # ... existing fanout logic ...
```

3. **Store responses when received:**
```python
# In _request_interaction_async, after getting response:
if response and self.storage:
    self._store_response(request, response)
```

### Phase 2: LLM Completion Caching

**Goal:** Cache LLM completions in execution log so reruns are deterministic.

**Approach:**
- Execution log already exists (ProcedureMetadata.execution_log)
- Add LLM completions to checkpoints
- On resume, replay cached completions

**Files to Modify:**

1. **`tactus/core/execution_context.py`** - Cache LLM completions:
```python
async def chat_completion(self, messages, ...):
    # Check if we have a cached completion for this position
    if self.storage and self.resume_mode:
        cached = self._get_cached_completion(position=self.current_checkpoint)
        if cached:
            logger.info(f"Using cached LLM completion at checkpoint {self.current_checkpoint}")
            return cached

    # Call LLM
    result = await self.client.create_completion(...)

    # Store in execution log for future resume
    if self.storage:
        self._store_completion(position=self.current_checkpoint, result=result)

    return result
```

### Phase 3: Checkpoint-Based Resume

**Goal:** Skip already-executed steps, resume from exact checkpoint.

**Approach:**
- Track execution position in Lua state
- On resume, fast-forward to the checkpoint position
- This is more complex and may require Lua coroutine management

## Test Plan

### Test 1: Basic HITL Resume (No LLM)

```lua
-- test-resume-basic.tac
function main()
    print("Step 1: Before HITL")
    local approved = Human.approve("Should we continue?")
    print("Step 2: After HITL, approved=" .. tostring(approved))
    return {approved = approved}
end
```

**Test Steps:**
1. Run: `tactus run test-resume-basic.tac`
2. Wait for "Should we continue?" prompt
3. Kill with Ctrl+C
4. Respond via control CLI: `tactus control --respond y`
5. Restart: `tactus run test-resume-basic.tac`
6. **Expected:** Should NOT print "Step 1" again, should continue from HITL
7. **Expected:** Should print "Step 2: After HITL, approved=true"

### Test 2: LLM + HITL Resume

```lua
-- test-resume-llm.tac
function main()
    print("Step 1: Calling LLM")
    local result = Agent.run({
        prompt = "Generate a random joke",
        model = "gpt-3.5-turbo"
    })
    print("Step 2: LLM returned: " .. result.output)

    print("Step 3: Asking for approval")
    local approved = Human.approve("Like this joke?")

    print("Step 4: Done, approved=" .. tostring(approved))
    return {joke = result.output, approved = approved}
end
```

**Test Steps:**
1. Run: `tactus run test-resume-llm.tac`
2. Let LLM complete, note the joke
3. Wait for approval prompt
4. Kill with Ctrl+C
5. Respond via control CLI: `tactus control --respond y`
6. Restart: `tactus run test-resume-llm.tac`
7. **Expected:** Should NOT call LLM again (cached completion)
8. **Expected:** Should show SAME joke as first run
9. **Expected:** Should skip to "Step 4: Done"

### Test 3: Multiple HITL Points

```lua
-- test-resume-multi.tac
function main()
    print("Step 1")
    local first = Human.approve("First question?")
    print("Step 2, first=" .. tostring(first))

    local second = Human.approve("Second question?")
    print("Step 3, second=" .. tostring(second))

    return {first = first, second = second}
end
```

**Test Steps:**
1. Run, respond to first question with 'y', kill at second question
2. Respond to second via control CLI: `tactus control --respond n`
3. Restart
4. **Expected:** Should skip first question (already answered)
5. **Expected:** Should use cached response for second question
6. **Expected:** Should complete immediately

## Success Criteria

✅ **Phase 1 Complete When:**
- Can kill at HITL prompt, respond via control CLI, restart, and continue
- Procedure doesn't rerun from start
- Stored response is used

✅ **Phase 2 Complete When:**
- LLM calls are cached in execution log
- Reruns use cached completions (deterministic)
- Can verify completion is identical across runs

✅ **Phase 3 Complete When:**
- Can handle multiple HITL points with partial progress
- Execution jumps to correct checkpoint position
- All prior state is properly restored

## Timeline Priority

**CRITICAL - Do This First:**
- Phase 1: Basic resume flow (essential infrastructure)
- Test 1: Verify basic HITL resume works

**HIGH - Do Next:**
- Phase 2: LLM caching (needed for determinism)
- Test 2: Verify LLM + HITL resume

**MEDIUM - Nice to Have:**
- Phase 3: Multi-checkpoint resume
- Test 3: Verify multiple HITL points

## Notes

- Storage backend already supports `get_state()` and `set_state()`
- Execution log structure already exists in `ProcedureMetadata`
- The hard part is integrating the resume check at the right point in the runtime
- May need to add a "resume mode" flag to know we're resuming vs. fresh start
