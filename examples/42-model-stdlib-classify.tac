-- Example: Classification via stdlib LLMClassifier (Model-backed)

Procedure {
    input = {
        text = field.string{required = true}
    },
    output = {
        label = field.string{required = true},
        confidence = field.number{required = true}
    },
    function(input)
        local classify = require("tactus.classify")

        local classifier = classify.LLMClassifier:new {
            name = "sentiment",
            classes = {"positive", "negative", "neutral"},
            prompt = "Classify sentiment as positive, negative, or neutral.",
            model = "openai/gpt-4o-mini",
            temperature = 0.0,
            max_retries = 2,
        }

        local result = classifier:classify(input.text)

        return {
            label = result.value,
            confidence = result.confidence or 0.5,
        }
    end
}

Specification([[
Feature: Model-backed stdlib LLMClassifier
  Scenario: Classify a positive sentence
    Given the procedure has started
    And the input text is "I love this!"
    When the procedure runs
    Then the procedure should complete successfully
]])
