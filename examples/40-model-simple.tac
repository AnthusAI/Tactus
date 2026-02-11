-- Simple Classification Example
--
-- Demonstrates a simple text classification procedure.

Procedure {
    input = {
            text = field.string{required = true, description = "Text to classify"}
    },
    output = {
            classification = field.string{required = true, description = "Classification result"}
    },
    function(input)

    -- Simple classification based on text content
        local classification = "neutral"
        local text_lower = input.text:lower()

        if text_lower:find("hello") or text_lower:find("hi") then
            classification = "greeting"
        elseif text_lower:find("help") or text_lower:find("question") then
            classification = "inquiry"
        elseif text_lower:find("thanks") or text_lower:find("thank") then
            classification = "gratitude"
        end

        return {
            classification = classification
        }

    -- BDD Specifications
    end
}

Specification([[
Feature: Simple Classification
  Scenario: Classify greeting text
    Given the procedure has started
    And the input text is "Hello world"
    When the procedure runs
    Then the procedure should complete successfully
    And the output classification should exist
]])
