--[[
Agent-Driven HITL Example

This example demonstrates an agent that dynamically constructs HITL requests
using a tool. The agent decides what questions to ask based on context.

Scenario: Deployment Review Agent
- User provides deployment details (app, environment)
- Agent must ask human for approval using the ask_approval tool
- Agent constructs the approval question dynamically
- Success: Agent calls HITL tool exactly once and proceeds based on response

Run with: tactus run examples/95-agent-hitl.tac
--]]

local done = require("tactus.tools.done")

-- Define HITL approval toolset inline
Toolset "hitl_approval" {
    description = "Tools for requesting human input and approval",

    tools = {
        {
            name = "ask_approval",
            description = "Ask the human for deployment approval. Pass a clear message describing what needs approval.",
            input = {
                message = field.string{required = true, description = "The approval question to ask the human"}
            },
            handler = function(args)
                Log.info("[Agent → Human] Asking for approval: " .. args.message)

                -- Use Human.approve() to get approval
                local approved = Human.approve({
                    message = args.message
                })

                Log.info("[Human → Agent] Approval response: " .. tostring(approved))

                return {
                    approved = approved,
                    message = "Human " .. (approved and "approved" or "rejected") .. " the request"
                }
            end
        }
    }
}

deployment_reviewer = Agent {
    model = "gpt-4o-mini",
    provider = "openai",
    tool_choice = "required",

    system_prompt = [[You are a deployment review assistant.

Your job is to review deployment requests and ask the human for approval.

When you receive a deployment request:
1. Call the ask_approval tool with a clear message about what deployment you need approval for
2. Wait for the human response
3. Call the done tool with the approval result

Important: You MUST call ask_approval exactly once, then call done with the result.]],

    tools = {"hitl_approval", done}
}

Procedure {
    function(input)
        print("=== Agent-Driven HITL Example ===\n")

        -- Input validation
        local app_name = input.app_name or "MyApp"
        local environment = input.environment or "production"

        print("Deployment request:")
        print("  App: " .. app_name)
        print("  Environment: " .. environment)
        print("")

        -- Run the agent (it will call ask_approval tool and done tool)
        print("Invoking deployment review agent...")

        -- Format the initial message with deployment details
        local message = string.format(
            "Please review this deployment request:\n\nApp: %s\nEnvironment: %s\n\nFirst, list what tools you have available. Then call the ask_approval tool to get human approval.",
            app_name,
            environment
        )

        local max_turns = 5
        local turn_count = 0

        -- Run agent until done is called or max turns reached
        while not done.called() and turn_count < max_turns do
            turn_count = turn_count + 1

            -- Pass message on first turn
            if turn_count == 1 then
                deployment_reviewer(message)
            else
                deployment_reviewer()
            end
        end

        print("\nAgent execution complete.")

        -- Verify the agent called the ask_approval tool
        if not Tool.called("hitl_approval_ask_approval") then
            print("\n❌ SPEC VIOLATION: Agent did not call ask_approval tool")
            return {
                success = false,
                reason = "Agent did not ask for approval"
            }
        end

        print("\n✓ Agent successfully used HITL tool")

        -- Get the approval result
        local approval_result = Tool.last_result("hitl_approval_ask_approval")
        local done_result = done.called() and done.last_call() or nil

        print("\nApproval result:")
        if approval_result then
            if approval_result.error then
                print("  Error: " .. tostring(approval_result.error))
            else
                print("  Approved: " .. tostring(approval_result.approved))
                print("  Message: " .. tostring(approval_result.message))
            end
        end

        if done_result then
            print("\nDone called with reason: " .. tostring(done_result.args.reason))
        end

        -- Extract approval status safely
        local approved = false
        if approval_result and not approval_result.error then
            approved = approval_result.approved or false
        end

        return {
            success = true,
            app_name = app_name,
            environment = environment,
            approved = approved,
            done_called = done.called()
        }
    end
}
