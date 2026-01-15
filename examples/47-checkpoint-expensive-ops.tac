-- Expensive Operations Example
--
-- Demonstrates computation of expensive operations.
-- This is a simplified version that performs calculations directly.

Procedure {
    input = {
            iterations = field.number{description = "Number of iterations for calculation", default = 1000}
    },
    output = {
            result1 = field.number{required = true, description = "Sum of squares"},
            result2 = field.number{required = true, description = "Modular product"}
    },
    function(input)

    -- Calculate sum of squares
        local sum = 0
        for i = 1, input.iterations do
            sum = sum + i * i
        end

        -- Calculate modular product
        local product = 1
        for i = 1, input.iterations do
            product = (product * i) % 1000000007
        end

        return {
            result1 = sum,
            result2 = product
        }

    -- BDD Specifications
    end
}

Specification([[
Feature: Expensive Operations
  Scenario: Calculate sum and product
    Given the procedure has started
    And the input iterations is 100
    When the procedure runs
    Then the procedure should complete successfully
    And the output result1 should exist
    And the output result2 should exist
]])
