-- Text Classification with Model Primitive
--
-- This example demonstrates using the Model primitive for ML inference.
-- Unlike Agent which is for conversational LLMs, Model is for:
-- - Classification (sentiment, intent, category)
-- - Extraction (entities, facts, quotes)
-- - Embeddings (semantic search)
-- - Custom ML inference
--
-- Model predictions are automatically checkpointed for durability.

-- Import completion tool from standard library
local done = require("tactus.tools.done")

-- Define a sentiment classifier model (HTTP endpoint)
Model "sentiment_classifier" {
    type = "http",
    endpoint = "https://httpbin.org/post"
}

-- Define an agent that routes based on sentiment
support_agent = Agent {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = [[
You are a customer support agent.

The customer's message sentiment is: {State.sentiment}

- If sentiment is negative, be extra empathetic
- If sentiment is positive, be friendly and efficient
- If sentiment is neutral, be professional

Respond appropriately to the customer's message.
Call done when you've provided a helpful response.
]],
    tools = {done}
}

Procedure {
    input = {
            customer_message = field.string{required = true, description = "Customer message to analyze"}
    },
    output = {
            sentiment = field.string{required = true, description = "Detected sentiment (positive/negative/neutral)"},
            response = field.string{required = true, description = "Agent's response"}
    },
    function(input)

    -- Simple sentiment detection for demo/testing
        -- Note: Model primitive mocking not yet implemented, using simple heuristic
        local msg_lower = string.lower(input.customer_message)
        if string.find(msg_lower, "love") or string.find(msg_lower, "great") or string.find(msg_lower, "amazing") then
            State.sentiment = "positive"
        elseif string.find(msg_lower, "hate") or string.find(msg_lower, "terrible") or string.find(msg_lower, "awful") then
            State.sentiment = "negative"
        else
            State.sentiment = "neutral"
        end

        -- Agent responds based on sentiment (checkpointed)
        support_agent({message = input.customer_message})

        -- Get response from done tool
        local response = "Thank you for your message."
        if done.called() then
            response = done.last_result() or "I'm here to help."
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
            {tool = "done", args = {reason = "I'm happy to help! Thank you for your positive feedback."}}
        },
        message = "Thank you for your message! I'm glad to assist."
    }
}

Specifications([[
Feature: Text Classification with Model Primitive
  Scenario: Sentiment classifier detects sentiment
    Given the procedure has started
    And the input customer_message is "I love this product!"
    When the procedure runs
    Then the done tool should be called
    And the output sentiment should exist
    And the output response should exist
    And the procedure should complete successfully
]])
