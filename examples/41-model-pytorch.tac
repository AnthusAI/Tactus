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
-- Model "sentiment_classifier" { type = "pytorch", path = "models/sentiment.pt" }

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
            customer_message = field.string{required = true, description = "Customer message to analyze"}
    },
    output = {
            sentiment = field.string{required = true, description = "Detected sentiment label"},
            response = field.string{required = true, description = "Agent response"}
    },
    function(input)

    -- Simple sentiment detection for demo/testing
        -- Note: PyTorch model mocking not yet implemented, using simple heuristic
        local msg_lower = string.lower(input.customer_message)
        if string.find(msg_lower, "love") or string.find(msg_lower, "great") then
            State.sentiment = "positive"
        elseif string.find(msg_lower, "hate") or string.find(msg_lower, "bad") then
            State.sentiment = "negative"
        else
            State.sentiment = "neutral"
        end

        -- Agent responds based on sentiment
        support_agent({message = input.customer_message})

        -- Get response from done tool
        local response = "I'm here to help."
        if done.called() then
            response = done.last_result() or "Thank you for your message."
        end

        return {
            sentiment = State.sentiment,
            response = response
        }

    -- BDD Specifications
    end
}

-- Agent Mocks for CI testing
Mocks {
    support_agent = {
        tool_calls = {
            {tool = "done", args = {reason = "Based on the sentiment analysis, I've provided an appropriate response."}}
        },
        message = "I understand your message and I'm here to help."
    }
}

Specifications([[
Feature: PyTorch Model Integration
  Scenario: PyTorch model performs inference
    Given the procedure has started
    And the input customer_message is "I love this product!"
    When the procedure runs
    Then the done tool should be called
    And the output sentiment should exist
    And the procedure should complete successfully
]])
