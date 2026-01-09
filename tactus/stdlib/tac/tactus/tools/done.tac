--[[
tactus.tools.done: Signal task completion

Usage:
    local done = require("tactus.tools.done")

    -- In an agent's toolset
    agent = Agent {
        toolsets = {"done"},
        ...
    }

    -- Check if done was called
    if done.called() then
        local result = done.last_call()
    end
]]--

local done_tool = Tool {
    description = "Signal task completion",
    input = {
        reason = field.string{required = false, description = "Reason for completion"}
    },
    function(args)
        return {
            status = "completed",
            reason = args.reason or "Task completed",
            tool = "done"
        }
    end
}

return done_tool
