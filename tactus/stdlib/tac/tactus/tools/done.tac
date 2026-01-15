--[[
tactus.tools.done: Signal task completion

Usage:
    local done = require("tactus.tools.done")

    -- In an agent's toolset
    agent = Agent {
        tools = {"done"},
        ...
    }

    -- Check if done was called
    if done.called() then
        local result = done.last_call()
    end
]]--

-- Provide explicit name so the tool is recorded/mocked as "done"
return Tool {
    name = "done",
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
