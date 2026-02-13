-- LLM-Based Sentiment Classification using Model Primitive
--
-- Demonstrates using an LLM as a Model primitive for stateless classification.
-- The Model uses an Agent internally but presents a pure predict() interface.

Procedure {
    input = {
        text = field.string{required = true, description = "Text to classify"}
    },
    output = {
        sentiment = field.string{required = true, description = "Sentiment: positive, negative, or neutral"},
        confidence = field.number{required = true, description = "Confidence score (0-1)"}
    },
    function(input)

    -- Define an LLM-based sentiment classifier Model
    local classifier = Model "sentiment_classifier" {
        type = "llm",
        model = "openai/gpt-4o-mini",

        -- System prompt describes the classification task
        system_prompt = [[
You are a sentiment classifier. Given a text, classify it as positive, negative, or neutral.
Return your response as JSON in this exact format:
{"sentiment": "positive|negative|neutral", "confidence": 0.95}

Provide a confidence score between 0 and 1 indicating how confident you are in the classification.
        ]],

        -- Low temperature for consistent classification
        temperature = 0.0,

        -- Validate inputs and outputs
        input = { text = "string" },
        output = { sentiment = "string", confidence = "float" },

        -- Parse from end (after any chain-of-thought reasoning)
        parse_direction = "end",

        -- Retry up to 3 times if response is invalid
        retries = 3,
    }

    -- Call the model to classify the text
    local result = classifier({text = input.text})

    -- Model returns: { result = {...}, cost = {...}, usage = {...} }
    local classification = result.result

    -- Log cost information
    print("Classification cost: $" .. result.cost.total_cost)
    print("Tokens used: " .. result.usage.total_tokens ..
          " (prompt: " .. result.usage.prompt_tokens ..
          ", completion: " .. result.usage.completion_tokens .. ")")

    return {
        sentiment = classification.sentiment,
        confidence = classification.confidence
    }

    end
}

-- BDD Specification
Specification([[
Feature: LLM-Based Sentiment Classification
  Scenario: Classify positive sentiment
    Given the procedure has started
    And the input text is "I absolutely love this product! It's amazing!"
    When the procedure runs
    Then the procedure should complete successfully
    And the output sentiment should be "positive"
    And the output confidence should be greater than 0.7

  Scenario: Classify negative sentiment
    Given the procedure has started
    And the input text is "This is terrible. I hate it."
    When the procedure runs
    Then the procedure should complete successfully
    And the output sentiment should be "negative"
    And the output confidence should be greater than 0.7

  Scenario: Classify neutral sentiment
    Given the procedure has started
    And the input text is "The item is blue and weighs 5 pounds."
    When the procedure runs
    Then the procedure should complete successfully
    And the output sentiment should be "neutral"
]])
