-- Plexus Scorecard Inventory
-- Lists scorecards via Plexus MCP and returns a short summary

local done = require("tactus.tools.done")

scorecard_inventory_agent = Agent {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = [[
You are a reporting agent.
You must do exactly two tool calls in this order:
1) Call "plexus_plexus_scorecards_list" with arguments:
   - identifier: "{input.identifier}"
   - limit: "{input.limit}"
2) Call "done" with a reason string of the form: "Returned N scorecards"
   where N is the count of items in the tool response. Do not omit the reason.
Do not call any other tools. Do not retry.
]],
    initial_message = "List Plexus scorecards and report the count.",
    tools = {"plexus", done},
}

Procedure {
    input = {
        identifier = field.string{default = ""},
        limit = field.number{default = 10},
    },
    output = {
        success = field.boolean{required = true},
        message = field.string{required = false},
        scorecards = field.object{required = false},
        error = field.string{required = false},
    },
    function(input)
        Log.info("Starting Plexus scorecard inventory", {identifier = input.identifier, limit = input.limit})

        local max_turns = 3
        local turn_count = 0

        repeat
            scorecard_inventory_agent()
            turn_count = turn_count + 1
        until done.called() or turn_count >= max_turns

        local message = "Scorecard inventory completed"
        local scorecards = nil
        if Tool.called("plexus_plexus_scorecards_list") then
            scorecards = Tool.last_result("plexus_plexus_scorecards_list")
        end
        if scorecards == nil and Tool.called("plexus_scorecards_list") then
            scorecards = Tool.last_result("plexus_scorecards_list")
        end

        if type(scorecards) == "table" then
            message = "Returned " .. tostring(#scorecards) .. " scorecards"
        elseif done.called() then
            local call = done.last_call()
            if call and call.args and call.args.reason and call.args.reason ~= "" then
                message = tostring(call.args.reason)
            end
        end

        if Tool.called("plexus_plexus_scorecards_list") and done.called() then
            return {
                success = true,
                message = message,
                scorecards = scorecards
            }
        end

        local err = "Scorecards tool not called"
        if not done.called() then
            err = "Done tool not called"
        end

        return {
            success = false,
            error = err
        }
    end
}
