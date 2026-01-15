-- Factorial Example
--
-- Demonstrates a simple factorial calculation.
-- This is a simplified version that calculates factorial iteratively.

Procedure {
    input = {
            n = field.number{required = true, description = "Number to calculate factorial for"}
    },
    output = {
            result = field.number{required = true, description = "Factorial of n"}
    },
    function(input)

    -- Calculate factorial iteratively
        local result = 1
        for i = 2, input.n do
            result = result * i
        end

        return {
            result = result
        }

    -- BDD Specifications
    end
}

Specification([[
Feature: Factorial Calculation
  Scenario: Calculate factorial of 5
    Given the procedure has started
    And the input n is 5
    When the procedure runs
    Then the procedure should complete successfully
    And the output result should be 120
]])
