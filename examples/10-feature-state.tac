-- State Management Example
-- Demonstrates setting, getting, and incrementing state values

-- Agents (defined at top level - reusable across procedures)
agent("worker", {
    provider = "openai",
    system_prompt = "A simple worker agent",
    initial_message = "Starting state management example",
    toolsets = {},
})

-- Procedure with outputs defined inline
procedure({
    outputs = {
        success = {
            type = "boolean",
            required = true,
            description = "Whether the workflow completed successfully",
        },
        message = {
            type = "string",
            required = true,
            description = "Status message",
        },
        count = {
            type = "number",
            required = true,
            description = "Final count of processed items",
        },
    }
}, function()
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

-- BDD Specifications
specifications([[
Feature: State Management
  Demonstrate state operations in Tactus workflows

  Scenario: State operations work correctly
    Given the procedure has started
    When the procedure runs
    Then the procedure should complete successfully
    And the state items_processed should be 5
    And the output success should be True
    And the output count should be 5
]])
