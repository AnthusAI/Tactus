-- Recursive Sub-Procedure Example
--
-- Demonstrates recursive procedure calls with auto-checkpointing.
-- This example implements a factorial calculator using recursive
-- sub-procedure calls. Each recursive call is checkpointed.

main = procedure("main", {
    input = {
        n = {
            type = "number",
            required = true,
            description = "Number to calculate factorial for"
        }
    },
    output = {
        result = {
            type = "number",
            required = true,
            description = "Factorial of n"
        },
        depth = {
            type = "number",
            required = true,
            description = "Recursion depth reached"
        }
    },
    state = {
        recursion_depth = {type = "number", default = 0}
    }
}, function()
    -- Base case: factorial(0) = 1, factorial(1) = 1
    if input.n <= 1 then
        return {
            result = 1,
            depth = state.recursion_depth
        }
    end

    -- Recursive case: n! = n * (n-1)!
    state.recursion_depth = state.recursion_depth + 1

    -- Recursive call is auto-checkpointed
    local sub_result = Procedure.run("examples/45-sub-procedure-recursive.tac", {
        n = input.n - 1
    })

    local factorial = input.n * (sub_result.result or sub_result)

    return {
        result = factorial,
        depth = state.recursion_depth
    }
end)

-- BDD Specifications
specifications([[
Feature: Recursive Sub-Procedure Calls
  As a workflow developer
  I want to make recursive procedure calls
  So that I can implement algorithms that require recursion

  Scenario: Calculate factorial recursively
    Given the procedure has started
    And the input n is 5
    When the procedure executes recursively
    Then the result should be 120
    And the depth should be 4

  Scenario: Base case stops recursion
    Given the procedure has started
    And the input n is 1
    When the procedure executes
    Then the result should be 1
    And the depth should be 0
    And no recursive calls should be made

  Scenario: Recursive calls are checkpointed
    Given the procedure has started
    And the input n is 4
    When the procedure executes recursively
    Then the execution log should contain 3 procedure_call entries
    And the result should be 24

  Scenario: Recursion depth is limited
    Given the procedure has started
    And the input n is 10
    When the procedure executes recursively
    Then it should respect the max recursion depth limit
]])
