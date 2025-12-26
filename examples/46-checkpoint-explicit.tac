-- Explicit Checkpoint Example
--
-- Demonstrates using the checkpoint() primitive to manually save state.
-- Explicit checkpoints allow you to mark important points in your
-- workflow where state should be persisted, enabling more granular
-- control over durability.

main = procedure("main", {
    input = {
        numbers = {
            type = "array",
            required = true,
            description = "Array of numbers to process"
        }
    },
    output = {
        sum = {
            type = "number",
            required = true,
            description = "Sum of all numbers"
        },
        product = {
            type = "number",
            required = true,
            description = "Product of all numbers"
        },
        average = {
            type = "number",
            required = true,
            description = "Average of all numbers"
        }
    },
    state = {
        sum = {type = "number", default = 0},
        product = {type = "number", default = 1},
        count = {type = "number", default = 0},
        checkpoint_count = {type = "number", default = 0}
    }
}, function()
    -- Step 1: Calculate sum
    for i = 1, #input.numbers do
        state.sum = state.sum + input.numbers[i]
    end

    -- Explicit checkpoint after sum calculation
    checkpoint(function()
        state.checkpoint_count = state.checkpoint_count + 1
        return {step = "sum_complete", sum = state.sum}
    end)

    -- Step 2: Calculate product
    for i = 1, #input.numbers do
        state.product = state.product * input.numbers[i]
    end

    -- Explicit checkpoint after product calculation
    checkpoint(function()
        state.checkpoint_count = state.checkpoint_count + 1
        return {step = "product_complete", product = state.product}
    end)

    -- Step 3: Calculate average
    state.count = #input.numbers
    local average = state.sum / state.count

    -- Final checkpoint before returning
    checkpoint(function()
        state.checkpoint_count = state.checkpoint_count + 1
        return {step = "average_complete", average = average}
    end)

    return {
        sum = state.sum,
        product = state.product,
        average = average
    }
end)

-- BDD Specifications
specifications([[
Feature: Explicit Checkpoint Primitive
  As a workflow developer
  I want to manually checkpoint state at specific points
  So that I can control exactly when state is persisted

  Scenario: Explicit checkpoints are recorded
    Given the procedure has started
    And the input numbers is [2, 4, 6]
    When the procedure executes with explicit checkpoints
    Then the checkpoint_count state should be 3
    And the execution log should contain explicit_checkpoint entries
    And the output sum should be 12
    And the output product should be 48
    And the output average should be 4

  Scenario: Explicit checkpoints save intermediate state
    Given the procedure has started
    And the input numbers is [5, 10]
    When the sum calculation completes
    And an explicit checkpoint is created
    Then the checkpoint should save the sum state
    When the product calculation completes
    And another explicit checkpoint is created
    Then the checkpoint should save the product state

  Scenario: Checkpoints enable replay from any point
    Given the procedure has started
    And the input numbers is [3, 7, 11]
    When the procedure executes to the second checkpoint
    And the procedure is restarted
    Then execution should resume from the second checkpoint
    And previous checkpoint results should be replayed
]])
