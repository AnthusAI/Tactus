-- Text Classification with Model Primitive
--
-- This example demonstrates using the model() primitive for ML inference.
-- Unlike agent() which is for conversational LLMs, model() is for:
-- - Classification (sentiment, intent, category)
-- - Extraction (entities, facts, quotes)
-- - Embeddings (semantic search)
-- - Custom ML inference
--
-- Model predictions are automatically checkpointed for durability.

-- Define completion tool
tool("done", {
    description = "Signal completion of the task",
    input = {
        reason = field.string{required = true, description = "Completion message"}
    }
}, function(args)
    return "Done: " .. args.reason
end)

-- Define a sentiment classifier model (HTTP endpoint)
model "sentiment_classifier" field.http{}

-- Define an agent that routes based on sentiment
Agent "support_agent" {
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
    toolsets = {"done"}
}

input {
        customer_message = field.string{required = true, description = "Customer message to analyze"}
    }

output {
        sentiment = field.string{required = true, description = "Detected sentiment (positive/negative/neutral)"},
        response = field.string{required = true, description = "Agent's response"}
    }

-- 1. Classify sentiment with ML model (checkpointed)
    State.sentiment = Model("sentiment_classifier").predict({
        text = input.customer_message
    })

    -- 2. Agent responds based on sentiment (checkpointed)
    Support_agent.turn({inject = input.customer_message})

    return {
        sentiment = State.sentiment,
        response = Support_agent.output
    }

-- BDD Specifications
Specifications([[
Feature: Text Classification with Model Primitive
  Scenario: Sentiment classifier detects sentiment
    Given the procedure has started
    And the input customer_message is "I love this product!"
    When the Sentiment_classifier model predicts
    Then the state sentiment should not be "unknown"
    And the Support_agent agent takes turn
    And the done tool should be called
    And the output sentiment should exist
    And the output response should exist
]])
