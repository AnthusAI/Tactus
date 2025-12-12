-- Migrated from .tyml format to .tactus

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

-- BDD Specifications
specifications([[
Feature: Hello World Workflow
  Demonstrate basic Tactus workflow execution

  Scenario: Successful workflow completion
    Given the procedure has started
    When the procedure runs
    Then the procedure should complete successfully
    And the output success should be True
    And the output count should be 5
    And the state items_processed should be 5
]])
