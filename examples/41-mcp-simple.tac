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
greeter = Agent {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = [[
You are a friendly greeter.
Call the greet tool with the name "Alice" and then call done.
]],
    initial_message = "Greet Alice",
    toolsets = {
        "test_server_greet",
        "done"
    }
}

-- Execute procedure

Procedure {
    output = {
            result = field.string{description = "Result"}
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