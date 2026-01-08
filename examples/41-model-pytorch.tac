-- PyTorch Model Example
--
-- This example demonstrates using a PyTorch model for inference.
-- Note: Requires PyTorch to be installed: pip install torch
--
-- The model file would be created like this:
--   import torch
--   model = YourModel()
--   torch.save(model, "sentiment_classifier.pt")

-- Define completion tool
tool("done", {
    description = "Signal completion of the task",
    input = {
        reason = field.string{required = true, description = "Completion message"}
    }
}, function(args)
    return "Done: " .. args.reason
end)

-- Define a PyTorch sentiment classifier
-- (This requires the .pt file to exist and PyTorch to be installed)
-- Model "sentiment_classifier" { type = "pytorch", path = "models/sentiment.pt" }

Agent "support_agent" {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = [[
You are a customer support agent.

The detected sentiment is: {State.sentiment}

Respond appropriately based on the sentiment.
Call done when finished.
]],
    toolsets = {"done"}
}

input {
        customer_message = field.string{required = true, description = "Customer message to analyze"}
    }

output {
        sentiment = field.string{required = true, description = "Detected sentiment label"},
        response = field.string{required = true, description = "Agent response"}
    }

-- Classify sentiment with PyTorch model
    -- Input: tensor of word indices (for demo, just pass a simple tensor)
    State.sentiment = Sentiment_classifier.predict({1, 2, 3, 4, 5})

    -- Agent responds based on sentiment
    Support_agent.turn({inject = input.customer_message})

    return {
        sentiment = State.sentiment,
        response = Support_agent.output
    }

-- BDD Specifications
Specifications([[
Feature: PyTorch Model Integration
  Scenario: PyTorch model performs inference
    Given the procedure has started
    And PyTorch is installed
    And the model file exists
    When the Sentiment_classifier model predicts
    Then the state sentiment should be one of ["negative", "neutral", "positive"]
    And the Support_agent agent takes turn
    And the done tool should be called
]])
