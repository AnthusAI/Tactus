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
agent("greeter", {
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
})

-- Execute procedure
main = procedure("main", {}, function()
    Log.info("Testing MCP tool")
    
    -- Single turn should be enough
    Greeter.turn()
    
    if Tool.called("test_server_greet") then
        local greeting = Tool.last_result("test_server_greet")
        Log.info("Greeting received", {greeting = greeting})
    end
    
    if Tool.called("done") then
        return {
            success = true,
            message = "MCP tool test successful"
        }
    end
    
    return {
        success = false,
        error = "Done not called"
    }
end)

