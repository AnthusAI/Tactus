-- MCP Plexus Documentation Smoke Test
-- Validates Tactus MCP wiring using Plexus get_plexus_documentation tool

local done = require("tactus.tools.done")

-- Agent definition
mcp_docs_tester = Agent {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = [[
You are a test agent for MCP tool wiring.
You must do exactly two tool calls in this order:
1) Call the tool "plexus_get_plexus_documentation" with filename "score-yaml-format".
2) Call the done tool with a short summary. Include the doc length and any error.
Do not call any other tools. Do not retry even if an error occurs.
]],
    initial_message = "Run the MCP docs tool test now.",
    tools = {"plexus", done},
}

Procedure {
    output = {
        success = field.boolean{required = true},
        doc_length = field.number{required = true},
        message = field.string{required = false},
        error = field.string{required = false},
    },
    function(input)
        Log.info("Starting MCP docs smoke test")

        local max_turns = 3
        local turn_count = 0

        repeat
            mcp_docs_tester()
            turn_count = turn_count + 1
        until done.called() or turn_count >= max_turns

        local doc = nil
        if Tool.called("plexus_get_plexus_documentation") then
            doc = Tool.last_result("plexus_get_plexus_documentation")
        end

        local doc_length = 0
        if doc ~= nil then
            doc_length = string.len(tostring(doc))
        end

        local message = "MCP docs tool completed"
        if done.called() then
            local call = done.last_call()
            if call and call.args and call.args.reason and call.args.reason ~= "" then
                message = tostring(call.args.reason)
            end
        end

        if done.called() and Tool.called("plexus_get_plexus_documentation") and doc_length > 0 then
            return {
                success = true,
                doc_length = doc_length,
                message = message
            }
        end

        local err = "Docs tool not called"
        if not done.called() then
            err = "Done tool not called"
        elseif doc_length == 0 then
            err = "Docs tool returned empty response"
        end

        return {
            success = false,
            doc_length = doc_length,
            error = err
        }
    end
}
