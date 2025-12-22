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

-- Define agent with MCP tools
agent("calculator", {
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
    toolsets = {
        "test_server_add_numbers",
        "test_server_multiply",
        "done"
    }
})

-- Execute procedure
procedure({}, function()
    Log.info("Starting MCP server test")
    
    -- Let agent work through the calculation
    local max_turns = 5
    local turn_count = 0
    
    repeat
        Calculator.turn()
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
        
    until Tool.called("done") or turn_count >= max_turns
    
    if Tool.called("done") then
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
end)

