--[[
tactus.tools.log: Logging tool for agents

Usage:
    local log = require("tactus.tools.log")

    -- In an agent's toolset
    agent = Agent {
        tools = {"log"},
        ...
    }

This tool allows agents to log messages during execution.
Note: For direct logging in procedures, use the Log global directly:
    Log.info("message")
    Log.debug("message", {key = value})
]]--

local log_tool = Tool {
    name = "log",
    description = "Log a message during procedure execution",
    input = {
        message = field.string{required = true, description = "Message to log"},
        level = field.string{required = false, description = "Log level: debug, info, warn, error"},
        data = field.object{required = false, description = "Optional data to include"}
    },
    function(args)
        local level = args.level or "info"
        local data = args.data or {}

        -- Use the Log global which is injected by the runtime
        if level == "debug" then
            Log.debug(args.message, data)
        elseif level == "warn" then
            Log.warn(args.message, data)
        elseif level == "error" then
            Log.error(args.message, data)
        else
            Log.info(args.message, data)
        end

        return {
            logged = true,
            level = level,
            message = args.message
        }
    end
}

return log_tool
