-- Example: Various Tool Source Types
-- Demonstrates importing tools from different sources

-- 1. Standard Library Tools (via require)
local done = require("tactus.tools.done")

-- 2. Inline tool definition (log tool for demonstration)
log = Tool {
    name = "log",
    description = "Log a message during procedure execution",
    input = {
        message = field.string{required = true, description = "Message to log"},
        level = field.string{required = false, description = "Log level: debug, info, warn, error"}
    },
    function(args)
        local level = args.level or "info"
        if level == "info" then
            Log.info(args.message)
        elseif level == "warn" then
            Log.warn(args.message)
        elseif level == "error" then
            Log.error(args.message)
        else
            Log.debug(args.message)
        end
        return {logged = true, level = level, message = args.message}
    end
}

-- Note: file and http tools are not yet available in stdlib
-- file = require("tactus.file")
-- http = require("tactus.http")

-- 2. CLI Tool Wrapper (wraps git command)
-- Tool sources (e.g., `use = "cli.git"`) are supported, but they require the
-- underlying command to exist in the runtime environment.
-- git_status = Tool { use = "cli.git", description = "Get git repository status" }

-- 3. Plugin Tool (would need to be implemented)
-- calculate = Tool { use = "plugin.math.calculator" }

-- 4. MCP Server Tool (requires MCP server to be configured)
-- search = Tool { use = "mcp.brave-search" }

-- Agent that uses various tools
tool_demo = Agent {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = [[You are a helpful assistant that demonstrates using various tools.

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

    tools = {"log", "done"}
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

Specification([[
Feature: Tool Source Types
  Demonstrate loading tools from various sources

  Scenario: Tool demo completes successfully
    Given the procedure has started
    And the agent "tool_demo" responds with "I've completed the tool demonstration."
    And the agent "tool_demo" calls tool "log" with args {"level": "info", "message": "Demonstrating tools"}
    And the agent "tool_demo" calls tool "done" with args {"reason": "Tool demonstration completed successfully."}
    When the procedure runs
    Then the done tool should be called
    And the output result should exist
    And the procedure should complete successfully
]])
