-- State Management Example
-- Demonstrates setting, getting, and incrementing state values

-- Agents (defined at top level - reusable across procedures)
worker = Agent {
    provider = "openai",
    system_prompt = "A simple worker agent",
    initial_message = "Starting state management example",
    tools = {},
}

-- Procedure with outputs defined inline

Procedure {
    output = {
            success = field.boolean{required = true, description = "Whether the workflow completed successfully"},
            message = field.string{required = true, description = "Status message"},
            count = field.number{required = true, description = "Final count of processed items"},
    },
    function(input)

    Log.info("Starting state management example")

        -- Initialize state (metatable syntax)
        state.items_processed = 0

        -- Process items and track count
        for i = 1, 5 do
          State.increment("items_processed")
          Log.info("Processing item", {number = i})
        end

        -- Retrieve final state (metatable syntax)
        local final_count = state.items_processed
        Log.info("Completed processing", {total = final_count})

        return {
          success = true,
          message = "State management example completed successfully",
          count = final_count
        }

    -- BDD Specifications
    end
}

Specification([[
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
