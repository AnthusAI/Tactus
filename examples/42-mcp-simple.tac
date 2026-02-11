--[[
Example: Simple MCP Server Test

A minimal example showing MCP tool usage.

Prerequisites:
Configure test MCP server in .tactus/config.yml:

mcp_servers:
  test_server:
    command: "python"
    args: ["-m", "tests.fixtures.test_mcp_server"]
]]

-- Define agent with one MCP tool
local done = require("tactus.tools.done")

greeter = Agent {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = [[
You are a friendly greeter.
Call the greet tool with the name "Alice" and then call done.
	]],
    initial_message = "Greet Alice",
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

    Log.info("Testing MCP tool")

        -- Single turn should be enough
        greeter()

        if Tool.called("test_server_greet") then
            local greeting = Tool.last_result("test_server_greet")
            Log.info("Greeting received", {greeting = greeting})
        end

        if done.called() then
            return {
                success = true,
                message = "MCP tool test successful"
            }
        end

        return {
            success = false,
            error = "Done not called"
        }

    end
}

Specification([[
Feature: MCP tool usage

  Scenario: Greets via MCP tool and completes
    Given the procedure has started
    And the agent "greeter" responds with "Hello, Alice!"
    And the agent "greeter" calls tool "test_server_greet" with args {"name": "Alice"}
    And the agent "greeter" calls tool "done" with args {"reason": "Hello, Alice!"}
    When the procedure runs
    Then the output success should be true
    And the output message should be "MCP tool test successful"
]])
