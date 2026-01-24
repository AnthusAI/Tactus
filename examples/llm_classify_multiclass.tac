-- LLM Multi-Class Classification Example
-- Demonstrates proper BDD specifications with custom step definitions

-- Define custom steps with regex patterns
Step("a color classifier", function(ctx)
    ctx.classifier = Classify {
        method = "llm",
        classes = {"red", "blue", "green", "yellow", "orange"},
        prompt = "What color is described in this text? Choose from: red, blue, green, yellow, orange.",
        model = "openai/gpt-4o-mini",
        temperature = 0,
        max_retries = 3
    }
end)

Step("I classify the color in \"(.+)\"", function(ctx, text)
    ctx.result = ctx.classifier(text)
end)

Step("the color should be \"(.+)\"", function(ctx, expected)
    assert(ctx.result.value == expected,
        "Expected '" .. expected .. "' but got '" .. ctx.result.value .. "'")
end)

Step("I reset the color classifier", function(ctx)
    ctx.classifier.reset()
end)

-- BDD Specification
Specification([[
Feature: LLM Multi-Class Classification
  As a developer using Tactus
  I want to classify text into multiple categories
  So that I can categorize content by color

  Scenario: Ocean water is classified as blue
    Given a color classifier
    When I classify the color in "The ocean water is a deep blue"
    Then the color should be "blue"

  Scenario: Fire truck is classified as red
    Given a color classifier
    When I classify the color in "The fire truck is bright red"
    Then the color should be "red"

  Scenario: Grass is classified as green
    Given a color classifier
    When I classify the color in "Fresh grass is a vibrant green"
    Then the color should be "green"

  Scenario: Banana is classified as yellow
    Given a color classifier
    When I classify the color in "The banana is ripe and yellow"
    Then the color should be "yellow"
]])

-- Minimal procedure to satisfy framework requirement
Procedure {
    output = {
        result = field.string{required = true}
    },
    function(input)
        return {result = "Tests executed via BDD specification"}
    end
}
