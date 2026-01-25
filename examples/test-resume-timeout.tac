--[[
Test: Timeout Behavior with Checkpoint/Resume

This test verifies that timeout and default values work correctly with
checkpoint/resume. Tests both timeout scenario and response-before-timeout.

Run with: tactus run examples/test-resume-timeout.tac --storage file --storage-path /tmp/tactus-test-timeout --no-sandbox
--]]

function main()
    print("=== Timeout Behavior Test ===")
    print("")
    print("Testing approval with 5-second timeout...")
    print("")

    local approved = Human.approve({
        message = "Respond within 5 seconds (or timeout will use default=false)",
        timeout = 5,
        default = false
    })

    print("")
    print("Result: " .. tostring(approved))

    if approved then
        print("  (Response received before timeout)")
    else
        print("  (Timeout occurred - used default value)")
    end

    print("")
    print("=== Test Complete ===")

    return {
        approved = approved,
        test = "timeout-behavior"
    }
end
