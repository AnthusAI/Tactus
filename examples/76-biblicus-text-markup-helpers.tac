--[[
Example: Biblicus text markup helpers

Demonstrates stripping span tags, parsing spans, and summarizing context.

To run this example:
  tactus run examples/76-biblicus-text-markup-helpers.tac
]]--

local text = require("biblicus.text")

Procedure {
    output = {
        stripped = field.string{required = true},
        parsed_text = field.string{required = true},
        summary = field.string{required = true}
    },
    function(input)
        local marked_up = "Hello <span>world</span>."
        local stripped = text.strip_span_tags(marked_up)
        local spans = text.parse_span_markup(marked_up)
        local summaries = text.summarize_span_context(marked_up, {1})

        return {
            stripped = stripped,
            parsed_text = spans[1].text,
            summary = summaries[1]
        }
    end
}

Specification([[
Feature: Biblicus markup helpers example
  Scenario: Use markup helper functions
    Given the procedure has started
    When the procedure runs
    Then the procedure should complete successfully
    And the output stripped should be Hello world.
    And the output parsed_text should be world
    And the output summary should be Span 1: world
]])
