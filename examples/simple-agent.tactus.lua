-- Migrated from .tyml format to .tactus.lua

name("simple_agent")
version("1.0.0")
description("A simple example demonstrating agent interaction with LLM")

-- Outputs
output("greeting", {
    type = "string",
    required = true,
    description = "The greeting message from the agent",
})
output("completed", {
    type = "boolean",
    required = true,
    description = "Whether the agent completed successfully",
})

-- Agents
agent("greeter", {
    provider = "openai",
    system_prompt = [[You are a friendly assistant. When asked to greet someone, 
provide a warm, friendly greeting. When you're done, call 
the done tool with the greeting message.
]],
    initial_message = "Please greet the user with a friendly message",
    tools = {"done"},
})

-- Procedure
procedure(function()
    -- Simple Agent Example
    -- Demonstrates calling an LLM agent using Worker.turn()

    Log.info("Starting simple agent example")

    -- Have the agent turn once (calls LLM)
    -- This requires OPENAI_API_KEY to be set (from .tactus/config.yml or environment)
    Greeter.turn()

    -- Check if agent called the done tool
    if Tool.called("done") then
      local greeting = Tool.last_call("done").args.reason
      Log.info("Agent completed", {greeting = greeting})
  
      return {
        greeting = greeting,
        completed = true
      }
    else
      Log.warn("Agent did not call done tool")
      return {
        greeting = "Agent did not complete properly",
        completed = false
      }
    end

end)
