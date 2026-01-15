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

    -- 1. Classify sentiment with ML model (checkpointed)
        State.sentiment = Model("sentiment_classifier").predict({
            text = input.customer_message
        })

        -- 2. Agent responds based on sentiment (checkpointed)
        support_agent({message = input.customer_message})

        return {
            sentiment = State.sentiment,
            response = support_agent.output
        }

    -- BDD Specifications
    end
}

Specification([[
Feature: Text Classification with Model Primitive
  Scenario: Sentiment classifier detects sentiment
    Given the procedure has started
    And the input customer_message is "I love this product!"
    And the tool "sentiment_classifier" returns "positive"
    And the agent "support_agent" responds with "Thank you for your message! I'm glad to assist."
    And the agent "support_agent" calls tool "done" with args {"reason": "I'm happy to help! Thank you for your positive feedback."}
    When the procedure runs
    Then the done tool should be called
    And the output sentiment should exist
    And the output response should exist
    And the procedure should complete successfully
]])
