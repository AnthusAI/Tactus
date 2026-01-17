# Checkpoint/Resume Rigorous Testing Plan

## Goal
Validate that transparent durability works for all checkpoint types and edge cases before proceeding with IDE/Plexus integration.

## Phase 1: Core Testing

### Test 1: ✅ Basic HITL Resume - COMPLETE
**Status:** Working! Single `Human.approve()` kill/resume verified.

**What Works:**
- Checkpoint saved when waiting for HITL response
- Procedure can be killed and restarted
- Cached response is replayed on restart
- No prompt appears second time (transparent!)

### Test 2: Multiple Sequential HITL Calls
**Purpose:** Verify checkpoint system handles multiple HITL interactions correctly

**Test Procedure:** `examples/test-resume-multi-hitl.tac`
```lua
function main()
    print("Step 1: Starting multi-HITL test")

    -- First approval
    local approved1 = Human.approve({
        message = "First approval: Continue?",
        default = true
    })
    print("First approved: " .. tostring(approved1))

    -- Second approval
    local approved2 = Human.approve({
        message = "Second approval: Still good?",
        default = true
    })
    print("Second approved: " .. tostring(approved2))

    -- Input request
    local name = Human.input({
        message = "What's your name?",
        default = "Test User"
    })
    print("Name: " .. name)

    print("Step 2: All interactions complete")

    return {
        approved1 = approved1,
        approved2 = approved2,
        name = name
    }
end
```

**Test Scenarios:**
1. **Complete run** - Respond to all three, verify completes
2. **Resume after first** - Kill after first approval, respond, restart → should resume at second approval
3. **Resume after second** - Kill after second approval, respond, restart → should resume at input
4. **Resume with all cached** - Respond to all three while stopped, restart → should complete immediately

**Expected:**
- 3 checkpoint entries in execution_log (positions 0, 1, 2)
- `replay_index` increments correctly (0 → 1 → 2 → 3)
- Each restart resumes from correct position
- All three responses cached and replayed correctly

### Test 3: LLM Checkpoint/Resume
**Purpose:** Verify LLM completions are cached and deterministic on resume

**Test Procedure:** `examples/test-resume-llm.tac`
```lua
function main()
    print("Step 1: Before LLM call")

    local agent = Agent.create({
        model = "claude-3-5-sonnet-20241022",
        provider = "anthropic"
    })

    local response = agent:generate({
        prompt = "Write a haiku about checkpoints in three lines."
    })

    print("Step 2: LLM Response received")
    print("Haiku: " .. response)

    return {
        haiku = response
    }
end
```

**Test Scenarios:**
1. **First run** - Let LLM complete, verify checkpoint created
2. **Restart** - Run again with same storage → should use cached completion (NO API call)
3. **Verify determinism** - Output should be IDENTICAL both times

**Expected:**
- 1 checkpoint entry for LLM call
- Checkpoint result contains full LLM response
- Second run uses cached response (instant, no API latency)
- Both outputs match exactly

**Critical Check:** Look for API request logs - second run should have ZERO API calls!

### Test 4: Mixed Operations (LLM + HITL)
**Purpose:** Verify checkpoint system handles both LLM and HITL together

**Test Procedure:** `examples/test-resume-mixed.tac`
```lua
function main()
    print("Step 1: Starting mixed test")

    -- LLM generates content
    local agent = Agent.create({
        model = "claude-3-5-sonnet-20241022",
        provider = "anthropic"
    })

    local draft = agent:generate({
        prompt = "Write a one-sentence product description for a todo app."
    })
    print("Draft: " .. draft)

    -- Human reviews it
    local approved = Human.approve({
        message = "Approve this product description?",
        default = true
    })

    if not approved then
        print("Rejected, trying again...")
        draft = agent:generate({
            prompt = "Write a different one-sentence product description for a todo app."
        })
        print("Revised draft: " .. draft)
    end

    print("Step 2: Test complete")

    return {
        draft = draft,
        approved = approved
    }
end
```

**Test Scenarios:**
1. **First run, approve** - Let LLM complete, approve → verify both checkpoints
2. **Resume after LLM** - Kill after LLM but before HITL, restart → should skip LLM, show approval prompt
3. **Resume with both cached** - Respond while stopped, restart → should complete instantly with both cached
4. **First run, reject** - Let LLM complete, reject → second LLM call creates new checkpoint

**Expected:**
- 2 checkpoints on approve path (LLM, HITL)
- 3 checkpoints on reject path (LLM, HITL, LLM)
- Resume correctly handles either case
- LLM responses cached and deterministic

## Phase 2: Edge Cases

### Test 5: All HITL Types
**Purpose:** Verify all four HITL methods work with checkpoint/resume

**Test Procedure:** `examples/test-resume-hitl-types.tac`
```lua
function main()
    -- Test approve
    local approved = Human.approve({
        message = "Test approval"
    })

    -- Test input
    local name = Human.input({
        message = "Enter name",
        default = "Test"
    })

    -- Test review
    local review = Human.review({
        message = "Review this text",
        artifact = "Sample text for review",
        artifact_type = "text"
    })

    -- Test escalate (if needed)
    if not approved then
        Human.escalate({
            message = "Need assistance",
            metadata = {reason = "approval_denied"}
        })
    end

    return {
        approved = approved,
        name = name,
        review = review
    }
end
```

**Expected:** All four HITL types create checkpoints and resume correctly

### Test 6: Kill at Different Points
**Purpose:** Verify resume works from any checkpoint position

**Method:**
- Use `test-resume-multi-hitl.tac` (3 HITL calls)
- Kill and restart at each of these points:
  1. Before any HITL (fresh start)
  2. After 1st HITL cached
  3. After 2nd HITL cached
  4. After all 3 cached

**Expected:** Each scenario resumes from correct position, uses cached responses up to that point

### Test 7: Timeout Behavior
**Purpose:** Verify timeout/default values work with checkpoint/resume

**Test Procedure:** `examples/test-resume-timeout.tac`
```lua
function main()
    local approved = Human.approve({
        message = "Respond within 5 seconds",
        timeout = 5,
        default = false
    })

    print("Approved: " .. tostring(approved))

    return {approved = approved}
end
```

**Test Scenarios:**
1. **Timeout first run** - Let it timeout, verify default used, checkpoint created
2. **Resume after timeout** - Restart → should use cached timeout result
3. **Response before timeout** - Respond in time, verify checkpoint has actual response

### Test 8: Long-Running Procedures
**Purpose:** Verify checkpoint system scales to many checkpoints

**Test Procedure:** `examples/test-resume-many-checkpoints.tac`
```lua
function main()
    local results = {}

    for i = 1, 10 do
        print("Iteration " .. i)

        local approved = Human.approve({
            message = "Approve iteration " .. i .. "?",
            default = true
        })

        table.insert(results, approved)
    end

    return {results = results}
end
```

**Expected:**
- 10 checkpoint entries (positions 0-9)
- `replay_index` tracks correctly through all 10
- Resume from any position works
- Storage file size reasonable (< 1MB for 10 checkpoints)

## Implementation Order

1. **Test 2** (Multiple HITL) - Most critical for real-world use
2. **Test 3** (LLM) - Validates determinism beyond HITL
3. **Test 4** (Mixed) - Real-world pattern
4. **Tests 5-8** (Edge cases) - Verify robustness

## Success Criteria

**Core Tests (Must Pass):**
- ✅ All Phase 1 tests pass (1-4)
- ✅ Checkpoints created for all operation types
- ✅ Resume works from any checkpoint position
- ✅ Cached responses used correctly
- ✅ No duplicate API calls on resume

**Edge Cases (Should Pass):**
- ✅ All HITL types work (approve, input, review, escalate)
- ✅ Timeout/default behavior preserved
- ✅ Multiple checkpoints (10+) work efficiently

## Verification Commands

```bash
# Run test
tactus run examples/test-resume-multi-hitl.tac --storage file --storage-path /tmp/tactus-test

# Check checkpoint file
cat /tmp/tactus-test/<procedure_id>.json | jq '.execution_log | length'

# Verify replay_index
cat /tmp/tactus-test/<procedure_id>.json | jq '.replay_index'

# Check checkpoint types
cat /tmp/tactus-test/<procedure_id>.json | jq '.execution_log[].type'

# Verify cached responses
cat /tmp/tactus-test/<procedure_id>.json | jq '.execution_log[].result'
```

## Next Steps After Testing

Once all tests pass:
1. Document checkpoint/resume behavior in user guide
2. Create integration guide for embedding Tactus
3. Proceed with IDE integration (reference implementation)
4. Apply pattern to Plexus integration (custom control channel)
