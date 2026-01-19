--[[
Simple test of Human.approve() - Single approval request

Run with: tactus run examples/92-test-inputs-simple.tac
--]]

Procedure {
    function(input)
        print("Testing Human.approve() - Simple Test")

        print("\n=== APPROVAL TEST ===")
        local approved = Human.approve("Do you approve this action?")

        print("\nResult: " .. tostring(approved))

        if approved then
            print("✓ User approved!")
        else
            print("✗ User rejected.")
        end

        return {
            completed = true,
            approved = approved
        }
    end
}
