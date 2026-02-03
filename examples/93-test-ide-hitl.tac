--[[
Test HITL in Tactus IDE with approval, input, and select.

This tests the inline HITL UI components in the IDE.
Run this file from the IDE by clicking the "Run" button.
--]]

Procedure {
    function(input)
        print("Testing HITL in Tactus IDE")
        print("=" .. string.rep("=", 50))

        -- Test 1: Approval (shows buttons)
        print("\n[1/3] Testing approval...")
        local approved = Human.approval(
            "Should we continue with the test?",
            {
                {label = "Yes, Continue", value = true, style = "primary"},
                {label = "No, Stop", value = false, style = "danger"}
            }
        )
        print("✓ User decision: " .. (approved and "approved" or "rejected"))

        if not approved then
            print("User chose to stop. Exiting.")
            return {status = "cancelled"}
        end

        -- Test 2: Text Input (shows text field)
        print("\n[2/3] Testing text input...")
        local name = Human.input("What is your name?")
        print("✓ User provided name: " .. tostring(name))

        -- Test 3: Select (shows option buttons)
        print("\n[3/3] Testing select...")
        local color = Human.select(
            "What is your favorite color?",
            {
                {label = "Red", value = "red"},
                {label = "Blue", value = "blue"},
                {label = "Green", value = "green"},
                {label = "Yellow", value = "yellow"}
            }
        )
        print("✓ User selected color: " .. tostring(color))

        print("\n" .. string.rep("=", 50))
        print("All HITL tests completed successfully!")
        print("\nResults:")
        print("  • Approved: " .. tostring(approved))
        print("  • Name: " .. tostring(name))
        print("  • Color: " .. tostring(color))

        return {
            status = "success",
            approved = approved,
            name = name,
            color = color
        }
    end
}
