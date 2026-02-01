--[[
Example: Biblicus text.link

Demonstrates linking repeated spans with id/ref attributes.

To run this example:
  tactus run examples/73-biblicus-text-link.tac
]]--

local text = require("biblicus.text")

Mocks {
    ["biblicus.text.link"] = {
        returns = {
            marked_up_text = "Alice met <span id=\"link_1\">Bob</span> and <span ref=\"link_1\">Bob</span> waved.",
            spans = {
                {
                    index = 1,
                    start_char = 10,
                    end_char = 13,
                    text = "Bob",
                    attributes = {id = "link_1"}
                },
                {
                    index = 2,
                    start_char = 18,
                    end_char = 21,
                    text = "Bob",
                    attributes = {ref = "link_1"}
                }
            },
            warnings = {}
        }
    }
}

Procedure {
    input = {
        input_text = field.string{
            default = "Alice met Bob and Bob waved.",
            description = "Input text for linking"
        }
    },
    output = {
        marked_up_text = field.string{required = true},
        first_id = field.string{required = true},
        second_ref = field.string{required = true}
    },
    function(input)
        local result = text.link({
            text = input.input_text,
            client = {provider = "openai", model = "gpt-4o-mini"},
            prompt_template = "Link the repeated name Bob to its first mention. Wrap each occurrence of Bob only.",
            id_prefix = "link_",
        })

        return {
            marked_up_text = result.marked_up_text,
            first_id = result.spans[1].attributes.id,
            second_ref = result.spans[2].attributes.ref
        }
    end
}

Specification([[
Feature: Biblicus text linking example
  Scenario: Link repeated names
    Given the procedure has started
    When the procedure runs
    Then the procedure should complete successfully
    And the output first_id should be link_1
    And the output second_ref should be link_1
    And the output marked_up_text should be Alice met <span id="link_1">Bob</span> and <span ref="link_1">Bob</span> waved.
]])
