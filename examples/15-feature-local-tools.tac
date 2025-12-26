--[[
Example: Local Python Tool Plugins

Demonstrates loading tools from local Python files without requiring MCP servers.

To run this example:
1. Ensure .tactus/config.yml has tool_paths configured:
   tool_paths:
     - "./examples/tools"

2. Run: tactus run examples/15-feature-local-tools.tac --param task="Calculate mortgage for $300,000 at 6.5% for 30 years"
]]--

-- Agent with access to local tools
agent("assistant", {
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
    toolsets = {
        -- All local plugin tools (loaded from tool_paths in config)
        "plugin",

        -- Built-in done tool
        "done"
    }
})

-- Main workflow
main = procedure("main", {
    input = {
        task = {
            type = "string",
            default = "Calculate the mortgage payment for a $300,000 loan at 6.5% interest for 30 years",
        },
    },
    output = {
        answer = {
            type = "string",
            required = true,
            description = "The assistant's answer to the task",
        },
        completed = {
            type = "boolean",
            required = true,
            description = "Whether the task was completed successfully",
        },
    },
    state = {}
}, function()
    local result
    local max_turns = 5  -- Safety limit to prevent infinite loops
    local turn_count = 0

    repeat
        result = Assistant.turn()
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

    until Tool.called("done") or turn_count >= max_turns

    -- Store final result
    local answer
    if Tool.called("done") then
        answer = Tool.last_call("done").args.reason
    else
        -- Max turns reached - use last response
        answer = result.text
    end

    return {
        answer = answer,
        completed = Tool.called("done")
    }
end)

