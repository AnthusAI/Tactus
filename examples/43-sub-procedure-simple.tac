-- Sub-Procedure Auto-Checkpointing Example
--
-- Demonstrates how sub-procedure calls are automatically checkpointed.
-- When a procedure calls another procedure, the call is checkpointed
-- and on replay, the cached result is returned without re-executing.

-- Main procedure that calls a sub-procedure

input {
        numbers = field.array{required = true, description = "Array of numbers to process"}
    }

output {
        sum = field.number{required = true, description = "Sum of all numbers"},
        product = field.number{required = true, description = "Product of all numbers"}
    }

-- Call sum_procedure (this call is auto-checkpointed)
    State.sum_result = Procedure.run("examples/helpers/sum.tac", {
        values = input.numbers
    })

    -- Call product_procedure (this call is also auto-checkpointed)
    State.product_result = Procedure.run("examples/helpers/product.tac", {
        values = input.numbers
    })

    return {
        sum = State.sum_result,
        product = State.product_result
    }

-- BDD Specifications
Specifications([[
Feature: Sub-Procedure Auto-Checkpointing
  Scenario: Sub-procedure calls are checkpointed
    Given the procedure has started
    And the input numbers is [2, 3, 4]
    When the first sub-procedure executes
    Then the sum_result should be 9
    When the second sub-procedure executes
    Then the product_result should be 24
    And the output sum should be 9
    And the output product should be 24

  Scenario: Sub-procedure results are replayed from checkpoint
    Given the procedure has started
    And the input numbers is [5, 10]
    When the sub-procedures are executed
    And the procedure is restarted
    Then the sub-procedures should not re-execute
    And the output sum should be 15
    And the output product should be 50
]])
