--[[
Test: All HITL Types with Checkpoint/Resume

This test verifies that all four HITL methods (approve, input, review, escalate)
create checkpoints correctly and resume properly.

Run with: tactus run examples/test-resume-hitl-types.tac --storage file --storage-path /tmp/tactus-test-hitl-types --no-sandbox
--]]

function main()
    print("=== All HITL Types Test ===")
    print("")

    -- Test 1: approve
    print("Test 1: Human.approve()")
    local approved = Human.approve({
        message = "Do you approve this test?",
        default = true
    })
    print("  Result: " .. tostring(approved))
    print("")

    -- Test 2: input
    print("Test 2: Human.input()")
    local name = Human.input({
        message = "What is your name?",
        default = "TestUser"
    })
    print("  Result: " .. name)
    print("")

    -- Test 3: review
    print("Test 3: Human.review()")
    local artifact = "This is a sample document that needs review."
    local review = Human.review({
        message = "Please review this document",
        artifact = artifact,
        artifact_type = "text",
        options = {"approve", "request_changes", "reject"}
    })
    print("  Decision: " .. (review.decision or "none"))
    if review.feedback and review.feedback ~= "" then
        print("  Feedback: " .. review.feedback)
    end
    print("")

    -- Test 4: escalate (only if approval was denied)
    if not approved then
        print("Test 4: Human.escalate()")
        print("  (Approval was denied - escalating)")
        Human.escalate({
            message = "Need assistance - approval was denied",
            severity = "warning",
            metadata = {reason = "approval_denied", test = "hitl-types"}
        })
        print("  Escalation complete")
        print("")
    else
        print("Test 4: Human.escalate() - SKIPPED (approval was granted)")
        print("")
    end

    print("=== Test Complete ===")

    return {
        approved = approved,
        name = name,
        review_decision = review.decision,
        review_feedback = review.feedback,
        escalated = not approved,
        test = "hitl-types-complete"
    }
end
