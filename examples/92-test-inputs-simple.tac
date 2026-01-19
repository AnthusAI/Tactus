--[[
Simple test of Human.inputs() - Just one batch

Run with: tactus run examples/92-test-inputs-simple.tac
--]]

Procedure {
    function(input)
        print("Testing Human.inputs() - Simple Test")

        -- Collect just 2 inputs
        print("\n=== SIMPLE TEST ===")
        local result = Human.inputs({
            {
                id = "name",
                label = "Name",
                type = "input",
                message = "What is your name?",
                metadata = {placeholder = "Enter your name"}
            },
            {
                id = "confirmed",
                label = "Confirm",
                type = "approval",
                message = "Is this correct?"
            }
        })

        print("\nResult collected:")
        print("  Name: " .. tostring(result.name))
        print("  Confirmed: " .. tostring(result.confirmed))

        return {
            completed = true,
            result = result
        }
    end
}
