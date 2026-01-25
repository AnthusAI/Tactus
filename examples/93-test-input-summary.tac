--[[
Test input_summary Display in IDE

This example demonstrates the input_summary context display in HITL requests.
The procedure accepts inputs, then requests approval, allowing you to see
the procedure inputs displayed in the IDE HITL notification.

Run with: tactus run examples/93-test-input-summary.tac --user-name "Alice" --environment prod
--]]

Procedure {
    input = {
        user_name = field.string{required = true, description = "User requesting deployment"},
        environment = field.string{required = true, description = "Target environment (dev/staging/prod)"},
        version = field.string{default = "v1.0.0", description = "Version to deploy"},
        rollback = field.boolean{default = false, description = "Enable automatic rollback"}
    },
    function(input)
        print("Testing input_summary display in IDE HITL notifications\n")

        print("Procedure inputs received:")
        print("  User: " .. input.user_name)
        print("  Environment: " .. input.environment)
        print("  Version: " .. input.version)
        print("  Rollback enabled: " .. tostring(input.rollback))

        -- Request approval - this should show input_summary in IDE
        print("\nRequesting approval...")
        local approved = Human.approve(
            "Deploy " .. input.version .. " to " .. input.environment .. "?"
        )

        if approved then
            print("\nDeployment approved! Proceeding...")
            return {
                success = true,
                deployed_version = input.version,
                environment = input.environment,
                deployed_by = input.user_name
            }
        else
            print("\nDeployment rejected.")
            return {
                success = false,
                message = "User rejected deployment"
            }
        end
    end
}
