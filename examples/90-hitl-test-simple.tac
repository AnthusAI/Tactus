-- Simple HITL test with default value

function main()
    print("Testing HITL with default...")

    -- This should use default value when no input available
    local approved = Human.approve({
        message = "Auto-approve test (should use default)",
        default = true
    })

    print("Approved: " .. tostring(approved))

    return {
        completed = true,
        approved = approved
    }
end
