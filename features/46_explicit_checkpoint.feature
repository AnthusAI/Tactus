Feature: Explicit Checkpoint Primitive
  As a workflow developer
  I want to manually checkpoint state at specific points
  So that I can control when state is persisted and enable selective replay

  Background:
    Given a Tactus validation environment

  Scenario: checkpoint() function is available globally
    Given a Lua DSL file with content:
      """
      procedure({
        output = {result = {type = "number", required = true}},
        state = {}
      }, function()
        local result = checkpoint(function()
          return 42
        end)
        return {result = result}
      end)
      """
    When I validate the file
    Then validation should succeed

  Scenario: Explicit checkpoints save state
    Given a Lua DSL file with content:
      """
      procedure({
        input = {value = {type = "number", default = 10}},
        output = {result = {type = "number", required = true}},
        state = {computed = {type = "number", default = 0}}
      }, function()
        state.computed = checkpoint(function()
          return input.value * 2
        end)
        return {result = state.computed}
      end)
      """
    When I validate the file
    Then validation should succeed

  Scenario: Multiple explicit checkpoints
    Given a Lua DSL file with content:
      """
      procedure({
        input = {x = {type = "number", default = 5}},
        output = {
          step1 = {type = "number", required = true},
          step2 = {type = "number", required = true},
          step3 = {type = "number", required = true}
        },
        state = {}
      }, function()
        local step1 = checkpoint(function()
          return input.x + 10
        end)

        local step2 = checkpoint(function()
          return step1 * 2
        end)

        local step3 = checkpoint(function()
          return step2 + 5
        end)

        return {step1 = step1, step2 = step2, step3 = step3}
      end)
      """
    When I validate the file
    Then validation should succeed

  Scenario: Checkpointing expensive operations
    Given a Lua DSL file with content:
      """
      procedure({
        input = {iterations = {type = "number", default = 100}},
        output = {result = {type = "number", required = true}},
        state = {}
      }, function()
        local result = checkpoint(function()
          local sum = 0
          for i = 1, input.iterations do
            sum = sum + i
          end
          return sum
        end)
        return {result = result}
      end)
      """
    When I validate the file
    Then validation should succeed

  Scenario: Checkpoint with state updates
    Given a Lua DSL file with content:
      """
      procedure({
        output = {total = {type = "number", required = true}},
        state = {
          count = {type = "number", default = 0},
          sum = {type = "number", default = 0}
        }
      }, function()
        checkpoint(function()
          state.count = state.count + 1
          state.sum = state.sum + 10
          return {checkpoint = "step1"}
        end)

        checkpoint(function()
          state.count = state.count + 1
          state.sum = state.sum + 20
          return {checkpoint = "step2"}
        end)

        return {total = state.sum}
      end)
      """
    When I validate the file
    Then validation should succeed
    And the state_schema should contain field "count"
    And the state_schema should contain field "sum"

  Scenario: Checkpoint vs Checkpoint primitive
    Given a Lua DSL file with content:
      """
      procedure({
        output = {
          result = {type = "number", required = true},
          position = {type = "number", required = true}
        },
        state = {}
      }, function()
        -- Global checkpoint() function
        local result = checkpoint(function()
          return 100
        end)

        -- Checkpoint primitive for introspection
        local position = Checkpoint.next_position()

        return {result = result, position = position}
      end)
      """
    When I validate the file
    Then validation should succeed
