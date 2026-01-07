-- Simple Tactus procedure without agents for BDD testing
-- This example uses only state and stage primitives, no LLM calls required

-- Stages
Stages({"start", "middle", "end"})

-- Procedure with input, output, and state defined inline
Procedure "main" {
    input = {
        target_count = field.number{required = false, description = "Target counter value", default = 5},
    },
    output = {
        final_count = field.number{required = true, description = "Final counter value"},
        message = field.string{required = true, description = "Status message"},
    },
    state = {
        counter = field.number{description = "Working counter", default = 0},
        message = field.string{description = "Working message", default = ""}
    },
    function(input)
  -- Initialize
  Stage.set("start")

  -- Do work
  local target = input.target_count or 5
  for i = 1, target do
    State.set("counter", i)
  end

  -- Transition to middle
  Stage.set("middle")
  State.set("message", "halfway")

  -- Complete
  Stage.set("end")
  State.set("message", "complete")

  return {
    final_count = State.get("counter"),
    message = State.get("message")
  }
end
}

-- BDD Specifications
Specifications([[
Feature: Simple State Management
  Test basic state and stage functionality without agents

  Scenario: State updates correctly
    Given the procedure has started
    When the procedure runs
    Then the state counter should be 5
    And the state message should be complete
    And the stage should be end
    And the procedure should complete successfully

  Scenario: Stage transitions work
    Given the procedure has started
    When the procedure runs
    Then the stage should transition from start to middle
    And the stage should transition from middle to end

  Scenario: Iterations are tracked
    Given the procedure has started
    When the procedure runs
    Then the total iterations should be less than 10
]])

-- Custom steps can be added here if needed
-- step("custom assertion", function(input)
--   assert(State.get("counter") > 0)
-- end)

