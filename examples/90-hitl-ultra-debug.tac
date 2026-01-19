--[[
Ultra Debug HITL Example - Check if Human primitive exists
--]]

function main()
    print("=== ULTRA DEBUG ===")
    print("Checking if Human exists...")
    print("Human type: " .. type(Human))

    if Human == nil then
        print("ERROR: Human is nil!")
        return {error = "Human primitive not available"}
    end

    print("Human exists! Type: " .. type(Human))
    print("Human.approve type: " .. type(Human.approve))

    if type(Human.approve) ~= "function" then
        print("ERROR: Human.approve is not a function!")
        return {error = "Human.approve not callable"}
    end

    print("About to call Human.approve()...")

    -- Simple approval request
    local should_continue = Human.approve({
        message = "Would you like to continue?"
    })

    print("Human.approve() returned!")
    print("Result: " .. tostring(should_continue))
    print("Type: " .. type(should_continue))

    return {
        approved = should_continue,
        success = true
    }
end
