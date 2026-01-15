-- Structured Output Demo
-- Demonstrates using output for structured data extraction
-- and accessing result.output, result.usage

extractor = Agent {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = [[You extract city information. Return ONLY structured data with these fields:
- city: city name
- country: country name
- population: estimated population (number, optional)

Be concise and accurate.]],
    initial_message = "{input.query}",

    -- Structured output (aligned with pydantic-ai's output)
    output = {
        city = field.string{required = true},
        country = field.string{required = true},
        population = field.number{required = false}
    }
}

Procedure {
    input = {
        query = field.string{default = "Tell me about Paris"}
    },
    output = {
        city_data = field.object{required = true},
        tokens_used = field.number{required = true}
    },
    function(input)
        Log.info("Starting structured output demo", {query = input.query})

        -- Agent returns ResultPrimitive (not raw data)
        local result = extractor()

        -- Access structured data via result.output
        Log.info("Extracted city information", {
            city = result.output.city,
            country = result.output.country,
            population = result.output.population or "unknown"
        })

        -- Access token usage stats
        Log.info("Token usage", {
            prompt_tokens = result.usage.prompt_tokens,
            completion_tokens = result.usage.completion_tokens,
            total_tokens = result.usage.total_tokens
        })

        -- Note: new_messages() is not available on TactusResult in mock mode
        -- In real execution, conversation history is managed by the agent

        return {
            city_data = result.output,
            tokens_used = result.usage.total_tokens
        }
    end
}

-- BDD Specifications
Specification([[
Feature: Structured Output with Result Access
  Demonstrate structured output validation and result access

  Scenario: Extract structured city data
    Given the procedure has started
    And the agent "extractor" returns data {"city": "Paris", "country": "France", "population": 2161000}
    When the procedure runs
    Then the procedure should complete successfully
    And the output city_data should exist
    And the output tokens_used should exist
]])
