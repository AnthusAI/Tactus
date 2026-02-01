--[[
Example: Biblicus text.annotate

Demonstrates annotation with a span attribute using mock markup.

To run this example:
  tactus run examples/69-biblicus-text-annotate.tac
]]--

local text = require("biblicus.text")

Mocks {
    ["biblicus.text.annotate"] = {
        returns = {
            marked_up_text = "Ada wrote <span label=\"artifact\">code</span>.",
            spans = {
                {
                    index = 1,
                    start_char = 10,
                    end_char = 14,
                    text = "code",
                    attributes = {label = "artifact"}
                }
            },
            warnings = {}
        }
    }
}

Procedure {
    input = {
        input_text = field.string{
            default = "Ada wrote code.",
            description = "Input text for annotation"
        }
    },
    output = {
        marked_up_text = field.string{required = true},
        label = field.string{required = true}
    },
    function(input)
        local result = text.annotate({
            text = input.input_text,
            client = {provider = "openai", model = "gpt-4o-mini"},
            prompt_template = "Add a label attribute so the word code is labeled as artifact.",
            allowed_attributes = {"label"},
        })

        return {
            marked_up_text = result.marked_up_text,
            label = result.spans[1].attributes.label
        }
    end
}

Specification([[
Feature: Biblicus text annotation example
  Scenario: Annotate the code artifact
    Given the procedure has started
    When the procedure runs
    Then the procedure should complete successfully
    And the output label should be artifact
    And the output marked_up_text should be Ada wrote <span label="artifact">code</span>.
]])
