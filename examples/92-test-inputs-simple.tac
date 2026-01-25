--[[
Test Human.approve() with LLM agent response and tool execution

This example demonstrates:
1. Human approval request
2. LLM agent responding to the decision
3. Tool execution if approved

Run with: tactus run examples/92-test-inputs-simple.tac
--]]

-- Define a mock deployment tool
local function deploy_to_production()
    Log.info("Deploying application to production...")
    -- Simulate deployment steps
    Log.info("  - Building Docker image...")
    Log.info("  - Pushing to registry...")
    Log.info("  - Updating Kubernetes deployment...")
    Log.info("  - Running health checks...")
    Log.info("Deployment completed successfully!")

    return {
        success = true,
        deployment_id = "deploy-" .. os.time(),
        environment = "production",
        timestamp = os.date("%Y-%m-%d %H:%M:%S")
    }
end

-- Create an agent to handle the approval workflow
Assistant = Agent {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = [[You are a helpful deployment assistant.
You help users understand the outcome of their deployment approval decisions.
Be concise and professional in your responses.]],
    temperature = 0.7
}

Procedure {
    function(input)
        print("Testing Human.approve() with Agent Response\n")

        print("=== DEPLOYMENT APPROVAL WORKFLOW ===\n")

        -- Step 1: Request human approval
        print("Step 1: Requesting deployment approval...")
        local approved = Human.approve("Do you approve deployment to production?")

        print("\nHuman decision: " .. tostring(approved))

        -- Step 2: Agent responds to the decision
        print("\n Step 2: Agent processing decision...")
        local agent_response

        if approved then
            agent_response = Assistant(
                "The user has approved the production deployment. " ..
                "Provide a brief confirmation message and mention that deployment is starting."
            )

            print("\nAgent: " .. tostring(agent_response))

            -- Step 3: Execute deployment tool if approved
            print("\nStep 3: Executing deployment...")
            local deployment_result = deploy_to_production()

            -- Step 4: Agent summarizes the result
            print("\nStep 4: Agent summarizing result...")
            local summary = Assistant(
                "The deployment was executed with these results: " ..
                Json.encode(deployment_result) ..
                ". Provide a brief success summary for the user."
            )

            print("\nAgent: " .. tostring(summary))

            return {
                completed = true,
                approved = true,
                deployment = deployment_result,
                agent_summary = summary
            }
        else
            agent_response = Assistant(
                "The user has rejected the production deployment. " ..
                "Provide a brief acknowledgment and mention that no changes were made."
            )

            print("\nAgent: " .. tostring(agent_response))

            return {
                completed = true,
                approved = false,
                message = "Deployment cancelled by user",
                agent_summary = agent_response
            }
        end
    end
}
