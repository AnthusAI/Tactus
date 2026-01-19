--[[
Debug HITL Example - Add logging to see what's happening
--]]

function main()
    print("=== HITL DEBUG ===")
    print("About to call Human.approve()")

    -- Simple approval request
    local should_continue = Human.approve({
        message = "Would you like to continue?"
    })

    print("Human.approve() returned: " .. tostring(should_continue))
    print("Type: " .. type(should_continue))

    return {
        approved = should_continue
    }
end
