-- Migrated from .tyml format to .tactus.lua

name("hello_world")
version("1.0.0")
description("A simple \"Hello World\" example for Tactus")

-- Outputs
output("success", {
    type = "boolean",
    required = true,
    description = "Whether the workflow completed successfully",
})
output("message", {
    type = "string",
    required = true,
    description = "A greeting message",
})
output("count", {
    type = "number",
    required = true,
    description = "Number of items processed",
})

-- Agents
agent("worker", {
    provider = "openai",
    system_prompt = "You are a friendly worker",
    initial_message = "Hello! Starting procedure",
    tools = {},
})

-- Procedure
procedure(function()
    -- Hello World Example
    -- A simple introduction to Tactus procedures

    Log.info("Hello, Tactus!")

    -- Initialize state
    State.set("items_processed", 0)

    -- Process some items
    for i = 1, 5 do
      State.increment("items_processed")
      Log.info("Processing item", {number = i})
    end

    local final_count = State.get("items_processed")

    return {
      success = true,
      message = "Hello World example completed successfully",
      count = final_count
    }

end)
