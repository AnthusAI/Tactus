--[[
Simple HITL (Human-in-the-Loop) Example

This example demonstrates the basic HITL capabilities:
- Human.approve() for yes/no decisions
- Human.input() for collecting text input
- Human.review() for reviewing generated content

Run with: tactus examples/90-hitl-simple.tac
--]]

function main()
    print("Starting HITL demo...")

    -- 1. Simple approval request
    print("\n=== APPROVAL REQUEST ===")
    local should_continue = Human.approve({
        message = "Would you like to continue with the workflow?"
    })

    if not should_continue then
        print("User declined. Stopping workflow.")
        return {stopped = true}
    end

    print("User approved! Continuing...")

    -- 2. Input request
    print("\n=== INPUT REQUEST ===")
    local user_name = Human.input({
        message = "What is your name?",
        placeholder = "Enter your name..."
    })

    print("Hello, " .. user_name .. "!")

    -- 3. Input with options
    print("\n=== INPUT WITH OPTIONS ===")
    local color = Human.input({
        message = "What is your favorite color?",
        options = {
            {label = "Red", value = "red"},
            {label = "Blue", value = "blue"},
            {label = "Green", value = "green"}
        }
    })

    print("You chose: " .. color)

    -- 4. Review request
    print("\n=== REVIEW REQUEST ===")
    local generated_text = "This is a sample document that was generated."

    local review_result = Human.review({
        message = "Please review this generated document",
        artifact = generated_text,
        artifact_type = "document"
    })

    print("Review decision: " .. review_result.decision)
    if review_result.feedback then
        print("Feedback: " .. review_result.feedback)
    end

    -- 5. Final confirmation
    print("\n=== FINAL CONFIRMATION ===")
    local final_approval = Human.approve({
        message = "Complete the workflow and save results?",
        timeout = 60  -- 60 second timeout
    })

    if final_approval then
        print("Workflow completed successfully!")
        return {
            completed = true,
            user_name = user_name,
            favorite_color = color,
            review = review_result
        }
    else
        print("Workflow cancelled by user.")
        return {completed = false}
    end
end
