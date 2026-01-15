--[[
Example: MCP Server Integration

This example demonstrates how to use tools from an MCP server in Tactus.

Prerequisites:
1. Configure MCP server in .tactus/config.yml:

   mcp_servers:
     test_server:
       command: "python"
       args:
         - "-m"
         - "tests.fixtures.test_mcp_server"

2. The test MCP server provides these tools:
   - add_numbers(a, b) - Add two numbers
   - greet(name) - Greet someone
   - get_status() - Get server status
   - multiply(x, y) - Multiply two numbers

3. Tools are automatically prefixed with server name:
   - test_server_add_numbers
   - test_server_greet
   - test_server_get_status
   - test_server_multiply
]]

-- MCP Server Test Example

local done = require("tactus.tools.done")

-- Define agent with MCP tools
calculator = Agent {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = [[
You are a helpful calculator assistant.
You have access to mathematical tools from an MCP server.

IMPORTANT: After completing the calculation, you MUST call the done tool to finish.

Steps:
1. Use add_numbers to add 5 + 3
2. Use multiply to multiply the result by 2
3. Call done with the final answer
	]],
    initial_message = "Calculate (5 + 3) * 2 and call done when finished",
    tools = {"test_server", done},
}

-- Execute procedure

Procedure {
    output = {
            success = field.boolean{required = true},
            message = field.string{required = false},
            error = field.string{required = false},
    },
    function(input)

    Log.info("Starting MCP server test")

        -- Let agent work through the calculation
        local max_turns = 5
        local turn_count = 0

        repeat
            calculator()
            turn_count = turn_count + 1

            -- Log tool calls
            if Tool.called("test_server_add_numbers") then
                local result = Tool.last_result("test_server_add_numbers")
                Log.info("Addition completed", {result = result})
            end

            if Tool.called("test_server_multiply") then
                local result = Tool.last_result("test_server_multiply")
                Log.info("Multiplication completed", {result = result})
            end

        until done.called() or turn_count >= max_turns

        if done.called() then
            Log.info("Calculation complete!")
            return {
                success = true,
                message = "MCP tools worked correctly"
            }
        else
            Log.error("Max turns exceeded")
            return {
                success = false,
                error = "Did not complete in time"
            }
        end

    end
}

Specification([[
Feature: MCP server tools

  Scenario: Uses MCP-prefixed tools and completes
    Given the procedure has started
    And the agent "calculator" responds with "Working..."
    And the agent "calculator" calls tool "test_server_add_numbers" with args {"a": 5, "b": 3}
    And the agent "calculator" calls tool "test_server_multiply" with args {"x": 8, "y": 2}
    And the agent "calculator" calls tool "done" with args {"reason": "16"}
    When the procedure runs
    Then the output success should be true
    And the output message should be "MCP tools worked correctly"
]])
