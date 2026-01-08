-- Checkpointing Expensive Operations
--
-- Demonstrates using checkpoint() to cache results of expensive
-- operations. On replay, expensive operations are skipped and
-- cached results are returned instantly.

input {
        iterations = field.number{description = "Number of iterations for expensive calculation", default = 1000}
    }

output {
        result1 = field.number{required = true, description = "Result of first expensive operation"},
        result2 = field.number{required = true, description = "Result of second expensive operation"},
        total_time_saved = field.string{required = true, description = "Time saved by checkpointing"}
    }

-- Expensive operation 1: Checkpointed for replay
    local result1 = checkpoint(function(input)
        local sum = 0
        for i = 1, input.iterations do
            sum = sum + i * i
        end
        return sum
    end)

    -- Expensive operation 2: Also checkpointed
    local result2 = checkpoint(function(input)
        local product = 1
        for i = 1, input.iterations do
            product = (product * i) % 1000000007
        end
        return product
    end)

    -- Check how many checkpoints were replayed vs executed
    local time_saved = "N/A"
    if State.checkpoints_replayed > 0 then
        time_saved = "Replayed " .. State.checkpoints_replayed .. " expensive operations"
    else
        time_saved = "First run - no replay yet"
    end

    return {
        result1 = result1,
        result2 = result2,
        total_time_saved = time_saved
    }

-- BDD Specifications
Specifications([[
Feature: Checkpointing Expensive Operations
  As a workflow developer
  I want to checkpoint expensive operations
  So that they don't re-execute on replay

  Scenario: Expensive operations are checkpointed
    Given the procedure has started
    And the input iterations is 100
    When the first expensive operation executes
    Then it should be wrapped in a checkpoint
    When the second expensive operation executes
    Then it should also be wrapped in a checkpoint

  Scenario: Replayed checkpoints skip expensive work
    Given the procedure has started
    And the input iterations is 100
    When the procedure completes the first time
    And the procedure is replayed from checkpoint
    Then expensive operations should not re-execute
    And cached results should be returned instantly

  Scenario: Multiple expensive operations checkpoint independently
    Given the procedure has started
    And the input iterations is 50
    When multiple expensive operations execute
    Then each should have its own checkpoint
    And each can be replayed independently
]])
