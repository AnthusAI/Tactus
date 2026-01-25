# Manual Checkpoint/Resume Testing Guide

This guide covers manual testing procedures for validating checkpoint/resume behavior in complex scenarios.

## Test 6: Kill at Different Points

**Purpose:** Verify that procedures can resume from any checkpoint position.

**Test Procedure:** Use `examples/test-resume-many-checkpoints.tac` (10 HITL calls)

### Scenario 1: Resume from Checkpoint 0 (Fresh Start)

```bash
rm -rf /tmp/tactus-test-many
mkdir -p /tmp/tactus-test-many

# Run procedure and respond to all 10
tactus run examples/test-resume-many-checkpoints.tac \
  --storage file \
  --storage-path /tmp/tactus-test-many \
  --no-sandbox
```

Use IPC control in another terminal:
```bash
# Respond to all 10 iterations
for i in {1..10}; do
  printf "y\n" | tactus control --socket /tmp/tactus-control-test-resume-many-checkpoints.sock
  sleep 0.5
done
```

**Expected:** 10 checkpoints created, procedure completes.

### Scenario 2: Resume from Checkpoint 3

```bash
rm -rf /tmp/tactus-test-many
mkdir -p /tmp/tactus-test-many

# Run procedure in one terminal
tactus run examples/test-resume-many-checkpoints.tac \
  --storage file \
  --storage-path /tmp/tactus-test-many \
  --no-sandbox
```

In another terminal, respond to first 3 only:
```bash
for i in {1..3}; do
  printf "y\n" | tactus control --socket /tmp/tactus-control-test-resume-many-checkpoints.sock
  sleep 0.5
done
```

Now KILL the procedure (Ctrl+C in first terminal).

Check checkpoints:
```bash
cat /tmp/tactus-test-many/test-resume-many-checkpoints.json | jq '.execution_log | length'
# Should show: 3
```

Restart procedure:
```bash
tactus run examples/test-resume-many-checkpoints.tac \
  --storage file \
  --storage-path /tmp/tactus-test-many \
  --no-sandbox
```

In control terminal, respond to remaining 7:
```bash
for i in {4..10}; do
  printf "y\n" | tactus control --socket /tmp/tactus-control-test-resume-many-checkpoints.sock
  sleep 0.5
done
```

**Expected:**
- First 3 iterations skip prompts (use cached responses)
- Iterations 4-10 show prompts
- Procedure completes successfully
- Total of 10 checkpoints in file

### Scenario 3: Resume from Checkpoint 7

Same as Scenario 2, but respond to first 7 iterations before killing.

**Expected:**
- Iterations 1-7 skip prompts on resume
- Iterations 8-10 show prompts
- Procedure completes

### Scenario 4: Resume with All Checkpoints Cached

Respond to all 10 iterations while procedure is waiting, then restart.

**Expected:**
- All 10 iterations skip prompts
- Procedure completes instantly
- No HITL prompts shown (all cached)

## Test 7: Timeout Behavior

**Purpose:** Verify that timeout/default values work correctly with checkpoint/resume.

**Test Procedure:** `examples/test-resume-timeout.tac`

```lua
function main()
    print("Test with 5-second timeout")

    local approved = Human.approve({
        message = "Respond within 5 seconds",
        timeout = 5,
        default = false
    })

    print("Approved: " .. tostring(approved))

    return {approved = approved}
end
```

### Test Case 1: Timeout on First Run

```bash
rm -rf /tmp/tactus-test-timeout
mkdir -p /tmp/tactus-test-timeout

# Run procedure - DON'T RESPOND (let it timeout)
tactus run examples/test-resume-timeout.tac \
  --storage file \
  --storage-path /tmp/tactus-test-timeout \
  --no-sandbox
```

**Expected:**
- After 5 seconds, procedure uses default value (false)
- Checkpoint created with result=false, timed_out=true
- Procedure completes

Now restart:
```bash
tactus run examples/test-resume-timeout.tac \
  --storage file \
  --storage-path /tmp/tactus-test-timeout \
  --no-sandbox
```

**Expected:**
- Procedure uses cached timeout result (false)
- NO prompt shown
- Completes instantly

### Test Case 2: Response Before Timeout

```bash
rm -rf /tmp/tactus-test-timeout
mkdir -p /tmp/tactus-test-timeout

# Run procedure - RESPOND QUICKLY
tactus run examples/test-resume-timeout.tac \
  --storage file \
  --storage-path /tmp/tactus-test-timeout \
  --no-sandbox
```

In another terminal (within 5 seconds):
```bash
printf "y\n" | tactus control --socket /tmp/tactus-control-test-resume-timeout.sock
```

**Expected:**
- Procedure gets response before timeout
- Checkpoint created with result=true, timed_out=false
- Procedure completes

Now restart:
```bash
tactus run examples/test-resume-timeout.tac \
  --storage file \
  --storage-path /tmp/tactus-test-timeout \
  --no-sandbox
```

**Expected:**
- Procedure uses cached response (true)
- NO prompt shown
- Completes instantly

## Test 8: Many Checkpoints (Scale)

**Purpose:** Verify checkpoint system scales to many checkpoints.

**Test Procedure:** Use `examples/test-resume-many-checkpoints.tac` (10 checkpoints)

```bash
rm -rf /tmp/tactus-test-many
mkdir -p /tmp/tactus-test-many

# Complete full run
tactus run examples/test-resume-many-checkpoints.tac \
  --storage file \
  --storage-path /tmp/tactus-test-many \
  --no-sandbox
```

Respond to all 10 iterations via IPC.

**Verification:**

1. Check checkpoint count:
```bash
cat /tmp/tactus-test-many/test-resume-many-checkpoints.json | jq '.execution_log | length'
# Should show: 10
```

2. Check file size:
```bash
ls -lh /tmp/tactus-test-many/test-resume-many-checkpoints.json
# Should be reasonable (< 1MB for 10 checkpoints)
```

3. Examine checkpoint structure:
```bash
cat /tmp/tactus-test-many/test-resume-many-checkpoints.json | jq '.execution_log[] | {position, type}'
# Should show positions 0-9, all type: "hitl_approval"
```

4. Test resume:
```bash
tactus run examples/test-resume-many-checkpoints.tac \
  --storage file \
  --storage-path /tmp/tactus-test-many \
  --no-sandbox
```

**Expected:**
- All 10 checkpoints replayed instantly
- No prompts shown
- Procedure completes in < 1 second
- Output shows "All 10 iterations completed!"

## Success Criteria

**Test 6 (Kill at Different Points):**
- ✅ Can resume from any checkpoint position (0, 3, 7, 10)
- ✅ Cached responses used up to kill point
- ✅ New prompts shown after kill point
- ✅ Procedure completes successfully from any position

**Test 7 (Timeout Behavior):**
- ✅ Timeout result cached correctly (result + timed_out flag)
- ✅ Resume uses cached timeout result
- ✅ Response result cached correctly (result + response time)
- ✅ Resume uses cached response result

**Test 8 (Many Checkpoints):**
- ✅ 10 checkpoints created successfully
- ✅ File size reasonable (< 1MB)
- ✅ Resume works with all 10 checkpoints
- ✅ No performance degradation
- ✅ replay_index tracks correctly (0 → 10)

## Troubleshooting

### "No clients connected" warning

The IPC channel reports no clients when the control CLI isn't connected. This is expected if you're only using the CLI channel. You can ignore this warning.

### Procedure hangs at prompt

If running in background without tty, the CLI channel can't read stdin. Use the IPC channel via `tactus control` in a separate terminal.

### Checkpoint file not found

The procedure ID might have a prefix. Check `/tmp/tactus-control-*.sock` to see the actual socket name, then look for the corresponding JSON file in the storage path.

### Checkpoint count mismatch

Some checkpoints might be combined or optimized. The important thing is that resume works correctly, not the exact count.
