-- Example: Various Tool Source Types
-- Demonstrates importing tools from different sources

-- 1. Standard Library Tools (via require)
local done = require("tactus.tools.done")
local log = require("tactus.tools.log")
-- Note: file and http tools are not yet available in stdlib
-- file = require("tactus.file")
-- http = require("tactus.http")

-- 2. CLI Tool Wrapper (wraps git command)
git_status = Tool { use = "cli.git", description = "Get git repository status" }

-- 3. Plugin Tool (would need to be implemented)
-- calculate = Tool { use = "plugin.math.calculator" }

-- 4. MCP Server Tool (requires MCP server to be configured)
-- search = Tool { use = "mcp.brave-search" }

-- Agent that uses various tools
tool_demo = Agent {
    provider = "openai",
    model = "gpt-4o-mini",
    system_message = [[You are a helpful assistant that demonstrates using various tools.

Available tools:
- log: Log messages at different levels
- file: Perform file operations (read, write, list)
- http: Make HTTP requests
- done: Signal completion

When asked to demonstrate tools:
1. Use the log tool to log what you're about to do
2. Use the appropriate tool based on the request
3. Log the result
4. Call done when finished]],

    toolsets = {"done", "log", "file", "http"}
}

-- Main procedure

Procedure {
    input = {
            demo_type = field.string{
                default = "file",
                description = "Type of demo: file, http, or all"
            }
    },
    output = {
            result = field.string{required = true}
    },
    function(input)

    Log.info("Starting tool source demonstration", {demo_type = input.demo_type})

            -- Set up the initial message based on demo type
            local message = ""
            if input.demo_type == "file" then
                message = "Please demonstrate file operations: list files in the current directory, then call done."
            elseif input.demo_type == "http" then
                message = "Please demonstrate HTTP operations: make a GET request to https://httpbin.org/get, then call done."
            else
                message = "Please demonstrate logging at different levels (info and warning), then call done."
            end

            -- Run the agent
            local response = tool_demo({message = message})

            -- Wait for done to be called
            local max_turns = 5
            local turn_count = 1

            while not done.called() and turn_count < max_turns do
                response = tool_demo()
                turn_count = turn_count + 1
            end

            -- Get the result
            local result = "Demo completed"
            if done.called() then
                local call = done.last_call()
                if call and call.args then
                    -- Safely try to get reason
                    local ok, reason = pcall(function() return call.args["reason"] end)
                    if ok and reason then
                        result = reason
                    end
                end
            end

            return {
                result = result
            }

    -- BDD Specifications
    end
}

Specifications([[
Feature: Tool Source Types
  Demonstrate loading tools from various sources

  Scenario: File operations demo
    Given the procedure has started
    When the procedure runs with demo_type "file"
    Then the file tool should be called
    And the done tool should be called
    And the procedure should complete successfully

  Scenario: HTTP operations demo
    Given the procedure has started
    When the procedure runs with demo_type "http"
    Then the http tool should be called
    And the done tool should be called
    And the procedure should complete successfully

  Scenario: Logging demo
    Given the procedure has started
    When the procedure runs with demo_type "log"
    Then the log tool should be called
    And the done tool should be called
    And the procedure should complete successfully
]])
