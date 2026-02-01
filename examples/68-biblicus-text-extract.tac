--[[
Example: Biblicus text.extract

Demonstrates Biblicus-backed extraction with deterministic mock markup.

To run this example:
  tactus run examples/68-biblicus-text-extract.tac
]]--

local text = require("biblicus.text")

Mocks {
    ["biblicus.text.extract"] = {
        returns = {
            marked_up_text = "<span>Alice</span> met <span>Bob</span> in Paris.",
            spans = {
                {index = 1, start_char = 0, end_char = 5, text = "Alice"},
                {index = 2, start_char = 10, end_char = 13, text = "Bob"}
            },
            warnings = {}
        }
    }
}

Procedure {
    input = {
        input_text = field.string{
            default = "Alice met Bob in Paris.",
            description = "Input text for extraction"
        }
    },
    output = {
        marked_up_text = field.string{required = true},
        first_span = field.string{required = true},
        second_span = field.string{required = true}
    },
    function(input)
        local result = text.extract({
            text = input.input_text,
            client = {provider = "openai", model = "gpt-4o-mini"},
            prompt_template = "Extract the names mentioned in the text.",
        })

        return {
            marked_up_text = result.marked_up_text,
            first_span = result.spans[1].text,
            second_span = result.spans[2].text
        }
    end
}

Specification([[
Feature: Biblicus text extraction example
  Scenario: Extract names from text
    Given the procedure has started
    When the procedure runs
    Then the procedure should complete successfully
    And the output first_span should be Alice
    And the output second_span should be Bob
    And the output marked_up_text should be <span>Alice</span> met <span>Bob</span> in Paris.
]])
