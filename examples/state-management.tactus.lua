-- Migrated from .tyml format to .tactus.lua

name("state_management")
version("1.0.0")
description("Demonstrates state management operations in Tactus workflows")

-- Outputs
output("success", {
    type = "boolean",
    required = true,
    description = "Whether the workflow completed successfully",
})
output("message", {
    type = "string",
    required = true,
    description = "Status message",
})
output("count", {
    type = "number",
    required = true,
    description = "Final count of processed items",
})

-- Agents
agent("worker", {
    provider = "openai",
    system_prompt = "A simple worker agent",
    initial_message = "Starting state management example",
    tools = {},
})

-- Procedure
procedure(function()
    -- State Management Example
    -- Demonstrates setting, getting, and incrementing state values

    Log.info("Starting state management example")

    -- Initialize state
    State.set("items_processed", 0)

    -- Process items and track count
    for i = 1, 5 do
      State.increment("items_processed")
      Log.info("Processing item", {number = i})
    end

    -- Retrieve final state
    local final_count = State.get("items_processed")
    Log.info("Completed processing", {total = final_count})

    return {
      success = true,
      message = "State management example completed successfully",
      count = final_count
    }

end)
