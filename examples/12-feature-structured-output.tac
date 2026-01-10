-- Structured Output Demo
-- Demonstrates using output for structured data extraction
-- and accessing result.data, result.usage

extractor = Agent {
    provider = "openai",
    model = "gpt-4o-mini",
    system_message = [[You extract city information. Return ONLY structured data with these fields:
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

        -- Access structured data via result.data
        Log.info("Extracted city information", {
            city = result.data.city,
            country = result.data.country,
            population = result.data.population or "unknown"
        })

        -- Access token usage stats
        Log.info("Token usage", {
            prompt_tokens = result.usage.prompt_tokens,
            completion_tokens = result.usage.completion_tokens,
            total_tokens = result.usage.total_tokens
        })

        -- Access messages from this turn
        local new_msgs = result.new_messages()
        Log.info("Messages generated in this turn", {count = #new_msgs})

        -- Log first message (if any)
        if #new_msgs > 0 then
            Log.info("First message", {
                role = new_msgs[1].role,
                content_preview = string.sub(new_msgs[1].content, 1, 100)
            })
        end

        return {
            city_data = result.data,
            tokens_used = result.usage.total_tokens
        }
    end
}

-- BDD Specifications
Specifications([[
Feature: Structured Output with Result Access
  Demonstrate structured output validation and result access

  Scenario: Extract structured city data
    Given the procedure has started
    When the procedure runs
    Then the procedure should complete successfully
    And the output city_data should exist
    And the output tokens_used should exist
]])
