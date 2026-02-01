--[[
Example: Biblicus text.slice

Demonstrates slicing text into segments using mock markup.

To run this example:
  tactus run examples/75-biblicus-text-slice.tac
]]--

local text = require("biblicus.text")

Mocks {
    ["biblicus.text.slice"] = {
        returns = {
            marked_up_text = "First sentence.<slice/> Second sentence.",
            slices = {
                {index = 1, start_char = 0, end_char = 15, text = "First sentence."},
                {index = 2, start_char = 15, end_char = 32, text = " Second sentence."}
            },
            warnings = {}
        }
    }
}

Procedure {
    input = {
        input_text = field.string{
            default = "First sentence. Second sentence.",
            description = "Input text for slicing"
        }
    },
    output = {
        marked_up_text = field.string{required = true},
        first_slice = field.string{required = true},
        second_slice = field.string{required = true}
    },
    function(input)
        local result = text.slice({
            text = input.input_text,
            client = {provider = "openai", model = "gpt-4o-mini"},
            prompt_template = "Insert a single <slice/> marker between the two sentences.",
        })

        return {
            marked_up_text = result.marked_up_text,
            first_slice = result.slices[1].text,
            second_slice = result.slices[2].text
        }
    end
}

Specification([[
Feature: Biblicus text slicing example
  Scenario: Slice the sentences
    Given the procedure has started
    When the procedure runs
    Then the procedure should complete successfully
    And the output first_slice should be First sentence.
    And the output second_slice should be  Second sentence.
    And the output marked_up_text should be First sentence.<slice/> Second sentence.
]])
