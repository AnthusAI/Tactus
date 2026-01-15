--[[
Example: Using require() to import modules

Demonstrates organizing Tactus code across multiple files using Lua's require().
This example imports functions from two separate modules and uses them directly.

To run this example:
tactus run examples/64-require-modules.tac --param a=5 --param b=3 --param text="hello"

Note: require() paths are relative to the procedure file's directory.
]]--

-- Import modules using require()
-- Paths are relative to this file's directory (examples/)
local math_module = require("helpers/math_module")
local string_module = require("helpers/string_module")

-- Script-mode procedure that uses the imported modules directly
Procedure {
    input = {
        a = field.number{default = 10, description = "First number"},
        b = field.number{default = 20, description = "Second number"},
        text = field.string{default = "world", description = "Text to transform"}
    },
    output = {
        sum = field.string{required = true, description = "Result of adding a + b"},
        product = field.string{required = true, description = "Result of multiplying a * b"},
        uppercase_text = field.string{required = true, description = "Text converted to uppercase"},
        reversed_text = field.string{required = true, description = "Text reversed"}
    },
    function(input)
        -- Use the imported tool handlers directly
        local sum_result = math_module.add.handler({a = input.a, b = input.b})
        local product_result = math_module.multiply.handler({a = input.a, b = input.b})
        local upper_result = string_module.uppercase.handler({text = input.text})
        local reverse_result = string_module.reverse.handler({text = input.text})

        return {
            sum = sum_result,
            product = product_result,
            uppercase_text = upper_result,
            reversed_text = reverse_result
        }
    end
}

Specification([[
Feature: Require modules to organize code
  Demonstrate using require() to import functions from separate files

  Scenario: Use imported math functions with defaults
    Given the procedure has started
    When the procedure runs
    Then the procedure should complete successfully
    And the output uppercase_text should be WORLD
    And the output reversed_text should be dlrow
]])
