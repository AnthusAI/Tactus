-- Simple Model Example
--
-- Demonstrates the model() primitive for ML inference.
-- This example uses an HTTP endpoint for classification.

-- Define a simple text classifier
model "intent_classifier" field.http{}

input {
        text = field.string{required = true, description = "Text to classify"}
    }

output {
        classification = field.string{required = true, description = "Classification result"}
    }

-- Call the model for inference (automatically checkpointed)
    local result = Model("intent_classifier").predict({
        text = input.text
    })

    -- Extract classification from result
    -- For httpbin, it echoes back our POST data
    local classification = result.json and result.json.text or "unknown"

    return {
        classification = classification
    }

-- BDD Specifications
Specifications([[
Feature: Simple Model Inference
  Scenario: Model predicts classification
    Given the procedure has started
    And the input text is "Hello world"
    When the Intent_classifier model predicts
    Then the output classification should exist
]])
