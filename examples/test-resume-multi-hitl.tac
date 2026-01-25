--[[
Test: Multiple Sequential HITL Calls with Checkpoint/Resume

This test verifies that checkpoint/resume works correctly with multiple
Human interactions in sequence. Tests that replay_index increments properly
and each checkpoint is saved and replayed correctly.

Run with: tactus run examples/test-resume-multi-hitl.tac --storage file --storage-path /tmp/tactus-test
--]]

function main()
    print("Step 1: Starting multi-HITL test")

    -- First approval
    local approved1 = Human.approve({
        message = "First approval: Continue to step 2?",
        default = true
    })
    print("First approved: " .. tostring(approved1))

    if not approved1 then
        print("User declined at step 1. Stopping.")
        return {stopped_at = 1}
    end

    -- Second approval
    local approved2 = Human.approve({
        message = "Second approval: Continue to step 3?",
        default = true
    })
    print("Second approved: " .. tostring(approved2))

    if not approved2 then
        print("User declined at step 2. Stopping.")
        return {stopped_at = 2}
    end

    -- Input request
    local name = Human.input({
        message = "What's your name for the test?",
        default = "Test User"
    })
    print("Name entered: " .. name)

    print("Step 2: All interactions complete!")

    return {
        approved1 = approved1,
        approved2 = approved2,
        name = name,
        test = "multi-hitl-complete"
    }
end
