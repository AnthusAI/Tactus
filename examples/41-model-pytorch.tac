-- PyTorch Model Example
--
-- This example demonstrates using a PyTorch model for inference.
-- Note: Requires PyTorch to be installed: pip install torch
--
-- The model file would be created like this:
--   import torch
--   model = YourModel()
--   torch.save(model, "sentiment_classifier.pt")

-- Define a PyTorch sentiment classifier
-- (This requires the .pt file to exist and PyTorch to be installed)
model("sentiment_classifier", {
    type = "pytorch",
    path = "examples/models/sentiment_classifier.pt",
    device = "cpu",
    labels = {"negative", "neutral", "positive"}
})

agent("support_agent", {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = [[
You are a customer support agent.

The detected sentiment is: {state.sentiment}

Respond appropriately based on the sentiment.
Call done when finished.
]],
    tools = {"done"}
})

procedure({
    input = {
        customer_message = {
            type = "string",
            required = true,
            description = "Customer message to analyze"
        }
    },
    output = {
        sentiment = {
            type = "string",
            required = true,
            description = "Detected sentiment label"
        },
        response = {
            type = "string",
            required = true,
            description = "Agent response"
        }
    },
    state = {
        sentiment = {type = "string", default = "unknown"}
    }
}, function()
    -- Classify sentiment with PyTorch model
    -- Input: tensor of word indices (for demo, just pass a simple tensor)
    state.sentiment = Sentiment_classifier.predict({1, 2, 3, 4, 5})

    -- Agent responds based on sentiment
    Support_agent.turn({inject = input.customer_message})

    return {
        sentiment = state.sentiment,
        response = Support_agent.output
    }
end)

-- BDD Specifications
specifications([[
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
