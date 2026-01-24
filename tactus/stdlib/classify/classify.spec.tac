--[[
REFERENCE SPEC - Tests Python implementation

The primary Tactus (.tac) implementation and spec is now at:
  tactus/stdlib/tac/tactus/classify.spec.tac

This spec remains for:
- Testing Python fallback implementation
- Documentation reference
- Backwards compatibility verification
]]

--[[doc
# Classification Classes

Proper Lua class hierarchy for text classification:

- **BaseClassifier**: Abstract base class
- **LLMClassifier**: LLM-based classification with retry logic
- **FuzzyMatchClassifier**: String similarity matching

## Usage

```lua
-- Import classification classes
local classify = require("tactus.stdlib.classify")
local LLMClassifier = classify.LLMClassifier
local FuzzyMatchClassifier = classify.FuzzyMatchClassifier

-- LLM Classification
local classifier = LLMClassifier:new {
    classes = {"Yes", "No"},
    prompt = "Is this a question?",
    model = "openai/gpt-4o-mini"
}
local result = classifier:classify("How are you?")

-- Fuzzy Matching
local fuzzy = FuzzyMatchClassifier:new {
    expected = "hello",
    threshold = 0.8
}
local result = fuzzy:classify("helo")
```

## LLMClassifier Parameters

- `classes` (required): List of valid classification values
- `prompt` (required): Classification instruction
- `model`: Model identifier (e.g., "openai/gpt-4o-mini")
- `temperature`: LLM temperature (default: 0.3)
- `max_retries`: Maximum retry attempts (default: 3)
- `confidence_mode`: "heuristic" or "none" (default: "heuristic")

## FuzzyMatchClassifier Parameters

- `expected` (required): Expected string to match against
- `threshold`: Similarity threshold 0.0-1.0 (default: 0.8)
- `classes`: Output values (default: ["Yes", "No"])

## Confidence Warning

LLM self-assessed confidence is generally unreliable unless calibrated
for your specific use case. Consider using fuzzy matching or human
review for high-stakes decisions.
]]

-- Local state for test context
local test_state = {}

-- Custom step definitions
Step("an LLM classifier with classes (.+)", function(ctx, classes_str)
    local classes = {}
    for class in string.gmatch(classes_str, '"([^"]+)"') do
        table.insert(classes, class)
    end
    test_state.classifier_config = {
        classes = classes,
        model = "openai/gpt-4o-mini"
    }
    test_state.classifier_type = "llm"
end)

Step("prompt \"(.+)\"", function(ctx, prompt)
    test_state.classifier_config.prompt = prompt
end)

Step("a fuzzy classifier expecting \"(.+)\"", function(ctx, expected)
    test_state.classifier_config = {
        expected = expected
    }
    test_state.classifier_type = "fuzzy"
end)

Step("I create the classifier", function(ctx)
    if test_state.classifier_type == "llm" then
        test_state.classifier = LLMClassifier:new(test_state.classifier_config)
    elseif test_state.classifier_type == "fuzzy" then
        test_state.classifier = FuzzyMatchClassifier:new(test_state.classifier_config)
    else
        error("Unknown classifier type: " .. tostring(test_state.classifier_type))
    end
end)

Step("I classify \"(.+)\"", function(ctx, text)
    if not test_state.classifier then
        if test_state.classifier_type == "llm" then
            test_state.classifier = LLMClassifier:new(test_state.classifier_config)
        else
            test_state.classifier = FuzzyMatchClassifier:new(test_state.classifier_config)
        end
    end
    test_state.result = test_state.classifier:classify(text)
end)

Step("the result value should be \"(.+)\"", function(ctx, expected)
    assert(test_state.result, "No classification result found")
    assert(test_state.result.value == expected,
        "Expected '" .. expected .. "' but got '" .. tostring(test_state.result.value) .. "'")
end)

Step("the result should have a confidence score", function(ctx)
    assert(test_state.result, "No classification result found")
    assert(test_state.result.confidence ~= nil,
        "Expected confidence score but got nil")
    assert(type(test_state.result.confidence) == "number",
        "Confidence should be a number, got " .. type(test_state.result.confidence))
    assert(test_state.result.confidence >= 0.0 and test_state.result.confidence <= 1.0,
        "Confidence should be between 0 and 1, got " .. tostring(test_state.result.confidence))
end)

Step("the matched_text should be \"(.+)\"", function(ctx, expected)
    assert(test_state.result, "No classification result found")
    assert(test_state.result.matched_text == expected,
        "Expected matched_text '" .. expected .. "' but got '" .. tostring(test_state.result.matched_text) .. "'")
end)

-- BDD Specifications
Specification([[
Feature: Classification Class Hierarchy
  As a Tactus developer
  I want to use proper OOP classifiers
  So that I can extend and compose classification behavior

  Scenario: LLM binary classification
    Given an LLM classifier with classes "Yes" and "No"
    And prompt "Is this a question?"
    When I classify "How are you?"
    Then the result value should be "Yes"
    And the result should have a confidence score

  Scenario: LLM multi-class classification
    Given an LLM classifier with classes "positive", "negative", and "neutral"
    And prompt "What is the sentiment?"
    When I classify "I love this product!"
    Then the result value should be "positive"

  Scenario: LLM negative sentiment
    Given an LLM classifier with classes "positive", "negative", and "neutral"
    And prompt "What is the sentiment?"
    When I classify "This is terrible"
    Then the result value should be "negative"

  Scenario: LLM neutral sentiment
    Given an LLM classifier with classes "positive", "negative", and "neutral"
    And prompt "What is the sentiment?"
    When I classify "The sky is blue"
    Then the result value should be "neutral"

  Scenario: Fuzzy match with typo
    Given a fuzzy classifier expecting "hello"
    When I classify "helo"
    Then the result value should be "Yes"
    And the matched_text should be "hello"

  Scenario: Fuzzy match exact
    Given a fuzzy classifier expecting "hello"
    When I classify "hello"
    Then the result value should be "Yes"

  Scenario: Fuzzy match failure
    Given a fuzzy classifier expecting "hello"
    When I classify "goodbye"
    Then the result value should be "No"
]])

-- Minimal procedure
Procedure {
    output = {
        result = field.string{required = true}
    },
    function(input)
        return {result = "Classification class hierarchy specs executed"}
    end
}
