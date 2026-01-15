-- Helper Module Example
--
-- Demonstrates using helper functions for code reuse.
-- Helper functions can be defined inline or imported via require().

-- Main procedure that uses helper functions

Procedure {
    input = {
            numbers = field.array{required = true, description = "Array of numbers to process"}
    },
    output = {
            sum = field.number{required = true, description = "Sum of all numbers"},
            product = field.number{required = true, description = "Product of all numbers"}
    },
    function(input)

    -- Calculate sum using inline helper function
        local function calculate_sum(values)
            local total = 0
            for i, v in ipairs(values) do
                total = total + v
            end
            return total
        end

        -- Calculate product using inline helper function
        local function calculate_product(values)
            local result = 1
            for i, v in ipairs(values) do
                result = result * v
            end
            return result
        end

        return {
            sum = calculate_sum(input.numbers),
            product = calculate_product(input.numbers)
        }

    -- BDD Specifications
    end
}

Specification([[
Feature: Helper Module Composition
  Scenario: Calculate sum and product using helpers
    Given the procedure has started
    And the input numbers is [2, 3, 4]
    When the procedure runs
    Then the procedure should complete successfully
    And the output sum should be 9
    And the output product should be 24
]])
