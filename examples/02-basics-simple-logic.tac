-- Simple Tactus procedure without agents for BDD testing
-- This example uses only state primitives, no LLM calls required

-- Procedure with input, output, and state defined inline
Procedure {
    input = {
        target_count = field.number{
            required = false,
            description = "Target counter value",
            default = 5,
        },
    },
    output = {
        final_count = field.number{required = true, description = "Final counter value"},
        message = field.string{required = true, description = "Status message"},
    },
    function(input)
        local target = input.target_count or 5
        for i = 1, target do
            state.counter = i
        end

        state.message = "complete"
        return {final_count = state.counter, message = state.message}
    end
}

-- BDD Specifications
Specification([[
Feature: Simple State Management
  Test basic state functionality without agents

  Scenario: State updates correctly
    Given the procedure has started
    When the procedure runs
    Then the state counter should be 5
    And the state message should be complete
    And the procedure should complete successfully

  Scenario: Outputs are returned
    Given the procedure has started
    When the procedure runs
    Then the output should exist
    And the output final_count should be 5
    And the output message should be complete

  Scenario: Iterations are tracked
    Given the procedure has started
    When the procedure runs
    Then the total iterations should be less than 10
]])

-- Custom steps can be added here if needed
-- step("custom assertion", function(input)
--   assert(state.counter > 0)
-- end)
