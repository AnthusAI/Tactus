-- PyTorch Model Example
--
-- This example demonstrates using a PyTorch model for inference.
-- Note: Requires PyTorch to be installed: pip install torch
--
-- The model file would be created like this:
--   import torch
--   model = YourModel()
--   torch.save(model, "sentiment_classifier.pt")

-- Import completion tool from standard library
local done = require("tactus.tools.done")

-- Define a PyTorch sentiment classifier
-- (This requires the .pt file to exist and PyTorch to be installed)
Model "sentiment_classifier" { type = "pytorch", path = "models/sentiment.pt" }

support_agent = Agent {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = [[
You are a customer support agent.

The detected sentiment is: {State.sentiment}

	Respond appropriately based on the sentiment.
	Call done when finished.
	]],
    tools = {done}
}

Procedure {
    input = {
            customer_message = field.string{default = "I love this product!", description = "Customer message to analyze"}
    },
    output = {
            sentiment = field.string{required = true, description = "Detected sentiment label"},
            response = field.string{required = true, description = "Agent response"}
    },
    function(input)

    -- Classify sentiment with PyTorch model
        -- Input: tensor of word indices (for demo, just pass a simple tensor)
        State.sentiment = Model("sentiment_classifier").predict({1, 2, 3, 4, 5})

        -- Agent responds based on sentiment
        support_agent({message = input.customer_message})

        return {
            sentiment = State.sentiment,
            response = support_agent.output
        }

    -- BDD Specifications
    end
}

Specification([[
Feature: PyTorch Model Integration
  Scenario: PyTorch model performs inference
    Given the procedure has started
    And the tool "sentiment_classifier" returns "positive"
    And the agent "support_agent" responds with "I understand your message and I'm here to help."
    And the agent "support_agent" calls tool "done" with args {"reason": "Based on the sentiment analysis, I've provided an appropriate response."}
    When the procedure runs
    Then the done tool should be called
    And the output sentiment should exist
    And the procedure should complete successfully
]])
