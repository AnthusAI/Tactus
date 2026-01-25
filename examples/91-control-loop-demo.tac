--[[
Control Loop Demo (Future)

This example demonstrates the new omnichannel control loop architecture
where multiple channels can race to provide responses.

Current status: The control loop architecture is implemented but not yet
integrated into the runtime. This example shows the intended API.

Features demonstrated:
- Multiple channels racing (CLI, IDE, Tactus Cloud)
- First response wins
- Rich context for decision-making
- Namespace-based routing for authorization

Run with: tactus examples/91-control-loop-demo.tac
--]]

function main()
    print("Control Loop Demo")
    print("=================")
    print("")

    -- This example will work with the legacy HITL system for now
    -- Once the control loop is integrated, it will automatically use
    -- the new multi-channel architecture

    -- 1. Simple approval (namespace determines who can respond)
    print("Step 1: Requesting approval for deployment...")

    local deploy_approved = Human.approve({
        message = "Deploy version 2.1.0 to production?",
        namespace = "operations/deployments/production",  -- Only ops team can respond
        context = {
            version = "2.1.0",
            environment = "production",
            changes = "Bug fixes and performance improvements"
        }
    })

    if deploy_approved then
        print("✓ Deployment approved!")
    else
        print("✗ Deployment cancelled")
        return {deployed = false}
    end

    -- 2. Input request with rich context
    print("\nStep 2: Collecting deployment schedule...")

    local schedule = Human.input({
        message = "When should the deployment occur?",
        namespace = "operations/deployments/production",
        options = {
            {label = "Immediately", value = "now"},
            {label = "During next maintenance window", value = "maintenance"},
            {label = "Specific time", value = "scheduled"}
        }
    })

    print("Deployment scheduled for: " .. schedule)

    -- 3. Final review with full context
    print("\nStep 3: Final review before execution...")

    local final_review = Human.review({
        message = "Final review of deployment plan",
        namespace = "operations/deployments/production-final",  -- Requires senior approval
        artifact = {
            version = "2.1.0",
            environment = "production",
            schedule = schedule,
            checklist = {
                "Database backups verified",
                "Rollback plan prepared",
                "Monitoring alerts configured"
            }
        }
    })

    if final_review.decision == "approved" then
        print("✓ Final review approved!")
        print("\nExecuting deployment...")

        -- Simulate deployment
        print("Deploying version 2.1.0 to production...")
        print("Deployment complete!")

        return {
            deployed = true,
            version = "2.1.0",
            schedule = schedule,
            approved_by = final_review
        }
    else
        print("✗ Deployment rejected")
        print("Reason: " .. (final_review.feedback or "No reason provided"))
        return {deployed = false, reason = final_review.feedback}
    end
end
