--[[
Test Human.multiple() - Batched HITL Requests

This example demonstrates the Human.multiple() method which collects
multiple inputs in a single interaction with a unified UI (inline or modal).

Run with: tactus run examples/92-test-multiple.tac
--]]

Procedure {
    function(input)
        print("Testing Human.multiple() - Batched HITL Requests")

    -- Collect multiple inputs at once in a unified UI
    print("\n=== DEPLOYMENT CONFIGURATION ===")
    local deployment = Human.multiple({
        {
            id = "target",
            label = "Target",
            type = "select",
            message = "Which environment should we deploy to?",
            options = {"dev", "staging", "prod"},
            metadata = {mode = "single", style = "radio"}
        },
        {
            id = "confirmed",
            label = "Confirm",
            type = "approval",
            message = "Are you sure you want to proceed with this deployment?"
        },
        {
            id = "notes",
            label = "Notes",
            type = "input",
            message = "Any deployment notes? (optional)",
            required = false,
            metadata = {placeholder = "Enter deployment notes...", multiline = true}
        }
    })

    print("\nDeployment configuration collected:")
    print("  Target: " .. tostring(deployment.target))
    print("  Confirmed: " .. tostring(deployment.confirmed))
    print("  Notes: " .. tostring(deployment.notes or "none"))

    if not deployment.confirmed then
        print("\nDeployment cancelled by user.")
        return {completed = false}
    end

    -- Another example: User registration form
    print("\n=== USER REGISTRATION ===")
    local user_info = Human.multiple({
        {
            id = "name",
            label = "Name",
            type = "input",
            message = "Enter your full name",
            metadata = {placeholder = "John Doe"}
        },
        {
            id = "role",
            label = "Role",
            type = "select",
            message = "Select your role",
            options = {
                {label = "Developer", value = "dev"},
                {label = "Designer", value = "design"},
                {label = "Manager", value = "manager"}
            },
            metadata = {mode = "single", style = "radio"}
        },
        {
            id = "features",
            label = "Features",
            type = "select",
            message = "Which features do you want enabled?",
            options = {"dark_mode", "notifications", "analytics"},
            metadata = {mode = "multiple", min = 1}
        },
        {
            id = "agree_terms",
            label = "Terms",
            type = "approval",
            message = "Do you agree to the terms and conditions?"
        }
    })

    print("\nUser registration:")
    print("  Name: " .. tostring(user_info.name or "none"))
    print("  Role: " .. tostring(user_info.role or "none"))

    -- Features can be a table or string depending on selection
    local features_str = ""
    if type(user_info.features) == "table" then
        features_str = table.concat(user_info.features, ", ")
    else
        features_str = tostring(user_info.features or "none")
    end
    print("  Features: " .. features_str)
    print("  Agreed to terms: " .. tostring(user_info.agree_terms))

        return {
            completed = true,
            deployment = deployment,
            user_info = user_info
        }
    end
}
