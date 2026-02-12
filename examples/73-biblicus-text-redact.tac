--[[
Example: Biblicus text.redact

Demonstrates redaction with span tags using mock markup.

To run this example:
  tactus run examples/73-biblicus-text-redact.tac
]]--

local text = require("tactus.biblicus.text")

Mocks {
    ["biblicus.text.redact"] = {
        returns = {
            marked_up_text = "The <span>secret</span> is safe.",
            spans = {
                {index = 1, start_char = 4, end_char = 10, text = "secret"}
            },
            warnings = {}
        }
    }
}

Procedure {
    input = {
        input_text = field.string{
            default = "The secret is safe.",
            description = "Input text for redaction"
        }
    },
    output = {
        marked_up_text = field.string{required = true},
        redacted_text = field.string{required = true}
    },
    function(input)
        local result = text.redact({
            text = input.input_text,
            client = {provider = "openai", model = "gpt-4o-mini"},
            prompt_template = "Wrap the word secret in <span> tags and return the updated text.",
            redaction_types = nil,
        })

        return {
            marked_up_text = result.marked_up_text,
            redacted_text = result.spans[1].text
        }
    end
}

Specification([[
Feature: Biblicus text redaction example
  Scenario: Redact the secret
    Given the procedure has started
    When the procedure runs
    Then the procedure should complete successfully
    And the output redacted_text should be secret
    And the output marked_up_text should be The <span>secret</span> is safe.
]])
