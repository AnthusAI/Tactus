-- Test: Basic HITL Resume (No LLM)
--
-- This test verifies that checkpoint/resume works for HITL requests.
--
-- Test Steps:
-- 1. Run: tactus run examples/test-resume-basic.tac
-- 2. Wait for "Should we continue?" prompt
-- 3. Kill with Ctrl+C
-- 4. Respond via control CLI: tactus control --respond y
-- 5. Restart: tactus run examples/test-resume-basic.tac
--
-- Expected Behavior:
-- - Should NOT print "Step 1" again
-- - Should resume from checkpoint with cached response
-- - Should print "Step 2: After HITL, approved=true"
-- - Should complete immediately without prompting

function main()
    print("Step 1: Before HITL (should only see this on first run)")

    local approved = Human.approve({
        message = "Should we continue?",
        default = true
    })

    print("Step 2: After HITL, approved=" .. tostring(approved))
    print("Step 3: Test complete!")

    return {
        approved = approved,
        test = "resume-basic"
    }
end
