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

-- Define a sentiment classifier model (HTTP endpoint)
model("sentiment_classifier", {
    type = "http",
    endpoint = "https://api.example.com/classify/sentiment",
    timeout = 10.0
})

-- Define an agent that routes based on sentiment
agent("support_agent", {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = [[
You are a customer support agent.

The customer's message sentiment is: {state.sentiment}

- If sentiment is negative, be extra empathetic
- If sentiment is positive, be friendly and efficient
- If sentiment is neutral, be professional

Respond appropriately to the customer's message.
Call done when you've provided a helpful response.
]],
    tools = {"done"}
})

main = procedure("main", {
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
            description = "Detected sentiment (positive/negative/neutral)"
        },
        response = {
            type = "string",
            required = true,
            description = "Agent's response"
        }
    },
    state = {
        sentiment = {type = "string", default = "unknown"}
    }
}, function()
    -- 1. Classify sentiment with ML model (checkpointed)
    state.sentiment = Sentiment_classifier.predict({
        text = input.customer_message
    })

    -- 2. Agent responds based on sentiment (checkpointed)
    Support_agent.turn({inject = input.customer_message})

    return {
        sentiment = state.sentiment,
        response = Support_agent.output
    }
end)

-- BDD Specifications
specifications([[
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
