--[[
Example: Local Python Tool Plugins

Demonstrates loading tools from local Python files without requiring MCP servers.

To run this example:
1. Ensure .tactus/config.yml has tool_paths configured:
   tool_paths:
     - "./examples/tools"

2. Run: tactus run examples/15-feature-local-tools.tac --param task="Calculate mortgage for $300,000 at 6.5% for 30 years"
]]--

-- Import completion tool from standard library
local done = require("tactus.tools.done")

-- Agent with access to local tools
assistant = Agent {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = [[You are a helpful assistant with access to tools for calculations.

IMPORTANT WORKFLOW:
1. Read the user's question
2. Use the appropriate calculation tool (like calculate_mortgage) to get the answer
3. Immediately call the 'done' tool with the calculation result
4. DO NOT ask follow-up questions - just call done with the result

You MUST call the 'done' tool after getting the calculation result.]],
    initial_message = "{input.task}",
    tools = {
        -- All local plugin tools (loaded from tool_paths in config)
        "plugin",
        done,
    }
}

-- Main workflow
Procedure {
    input = {
        task = field.string{default = "Calculate the mortgage payment for a $300"},
    },
    output = {
        answer = field.string{required = true, description = "The assistant's answer to the task"},
        completed = field.boolean{required = true, description = "Whether the task was completed successfully"},
    },
    function(input)
        local result
        local max_turns = 5  -- Safety limit to prevent infinite loops
        local turn_count = 0

        repeat
            result = assistant()
            turn_count = turn_count + 1

            -- Log tool usage for visibility
            if Tool.called("calculate_mortgage") then
                Log.info("Used mortgage calculator")
            end
            if Tool.called("web_search") then
                Log.info("Performed web search")
            end
            if Tool.called("analyze_numbers") then
                Log.info("Analyzed numbers")
            end

        until done.called() or turn_count >= max_turns

        -- Store final result
        local answer
        if done.called() then
            local call = done.last_call()
            answer = "Task completed"
            if call and call.args then
                -- Safely try to get reason
                local ok, reason = pcall(function() return call.args["reason"] end)
                if ok and reason then
                    answer = reason
                end
            end
        else
            -- Max turns reached - use last response
            if result and result.output then
                answer = tostring(result.output)
            elseif result and result.message then
                answer = tostring(result.message)
            else
                answer = ""
            end
        end

        return {
            answer = answer,
            completed = done.called()
        }
    end
}

Specification([[
Feature: Local tools

  Scenario: Uses local calculation tool and completes
    Given the procedure has started
    And the input task is "Calculate mortgage for $300,000 at 6.5% for 30 years"
    And the agent "assistant" responds with "Monthly payment is $1,896.20 (mocked)."
    And the agent "assistant" calls tool "calculate_mortgage" with args {"principal": 300000, "annual_interest_rate": 0.065, "years": 30}
    And the agent "assistant" calls tool "done" with args {"reason": "Monthly payment is $1,896.20 (mocked)."}
    When the procedure runs
    Then the output answer should be "Monthly payment is $1,896.20 (mocked)."
    And the output completed should be true
]])
