-- Simple Model Example
--
-- Demonstrates the model() primitive for ML inference.
-- This example uses an HTTP endpoint for classification.

-- Define a simple text classifier
model("intent_classifier", {
    type = "http",
    endpoint = "https://httpbin.org/post",  -- Using httpbin for testing
    timeout = 10.0
})

main = procedure("main", {
    input = {
        text = {
            type = "string",
            required = true,
            description = "Text to classify"
        }
    },
    output = {
        classification = {
            type = "string",
            required = true,
            description = "Classification result"
        }
    },
    state = {}
}, function()
    -- Call the model for inference (automatically checkpointed)
    local result = Intent_classifier.predict({
        text = input.text
    })

    -- Extract classification from result
    -- For httpbin, it echoes back our POST data
    local classification = result.json and result.json.text or "unknown"

    return {
        classification = classification
    }
end)

-- BDD Specifications
specifications([[
Feature: Simple Model Inference
  Scenario: Model predicts classification
    Given the procedure has started
    And the input text is "Hello world"
    When the Intent_classifier model predicts
    Then the output classification should exist
]])
