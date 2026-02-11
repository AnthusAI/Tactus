-- Math Operations Example
--
-- Demonstrates calculating sum, product, and average.

Procedure {
    input = {
            numbers = field.array{required = true, description = "Array of numbers to process"}
    },
    output = {
            sum = field.number{required = true, description = "Sum of all numbers"},
            product = field.number{required = true, description = "Product of all numbers"},
            average = field.number{required = true, description = "Average of all numbers"}
    },
    function(input)

    -- Calculate sum
        local sum = 0
        for i = 1, #input.numbers do
            sum = sum + input.numbers[i]
        end

        -- Calculate product
        local product = 1
        for i = 1, #input.numbers do
            product = product * input.numbers[i]
        end

        -- Calculate average
        local average = sum / #input.numbers

        return {
            sum = sum,
            product = product,
            average = average
        }

    -- BDD Specifications
    end
}

Specification([[
Feature: Math Operations
  Scenario: Calculate sum, product and average
    Given the procedure has started
    And the input numbers is [2, 4, 6]
    When the procedure runs
    Then the procedure should complete successfully
    And the output sum should be 12
    And the output product should be 48
    And the output average should be 4
]])
