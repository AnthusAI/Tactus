-- LLM Binary Classification Example
-- Demonstrates proper BDD specifications with custom step definitions

-- Define custom steps with regex patterns
Step("a binary classifier asking \"(.+)\"", function(ctx, prompt)
    ctx.classifier = Classify {
        method = "llm",
        classes = {"Yes", "No"},
        prompt = prompt,
        model = "openai/gpt-4o-mini",
        temperature = 0,
        max_retries = 3
    }
end)

Step("I classify \"(.+)\"", function(ctx, text)
    ctx.result = ctx.classifier(text)
end)

Step("the result should be \"(.+)\"", function(ctx, expected)
    assert(ctx.result.value == expected,
        "Expected '" .. expected .. "' but got '" .. ctx.result.value .. "'")
end)

Step("confidence should be greater than (.+)", function(ctx, threshold)
    local thresh = tonumber(threshold)
    assert(ctx.result.confidence > thresh,
        "Expected confidence > " .. threshold .. " but got " .. ctx.result.confidence)
end)

Step("I reset the classifier", function(ctx)
    ctx.classifier.reset()
end)

-- BDD Specification
Specification([[
Feature: LLM Binary Classification
  As a developer using Tactus
  I want to classify text with a binary LLM classifier
  So that I can make Yes/No decisions based on content

  Scenario: Blue sky is classified as Yes
    Given a binary classifier asking "Is the sky blue? Answer Yes or No."
    When I classify "The sky is a beautiful blue color today"
    Then the result should be "Yes"
    And confidence should be greater than 0.5

  Scenario: Sunset sky is classified as No
    Given a binary classifier asking "Is the sky blue? Answer Yes or No."
    When I classify "The sky is red and orange at sunset"
    Then the result should be "No"

  Scenario: Clear blue sky is classified as Yes
    Given a binary classifier asking "Is the sky blue? Answer Yes or No."
    When I classify "Looking up, I see a clear blue sky"
    Then the result should be "Yes"
]])

-- Minimal procedure just to satisfy the Procedure requirement
Procedure {
    output = {
        result = field.string{required = true}
    },
    function(input)
        return {result = "Tests executed via BDD specification"}
    end
}
