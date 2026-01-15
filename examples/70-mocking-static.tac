-- Example: Static Mocking
-- Demonstrates basic static mocking where tools always return the same value

-- Import completion tool from standard library
local done = require("tactus.tools.done")

-- Define the tools we'll mock (with dummy handlers since they'll be mocked)
weather = Tool {
    description = "Get current weather information",
    input = {
        location = field.string{default = "San Francisco"}
    },
    function(input)
        -- This won't be called when mocked
        return {temperature = 0, conditions = "Unknown"}
    end
}

stock_price = Tool {
    description = "Get current stock price",
    input = {
        symbol = field.string{default = "AAPL"}
    },
    function(input)
        -- This won't be called when mocked
        return {price = 0, change = 0}
    end
}

-- Static mocks - always return the same response
Mocks {
    weather = {
        returns = {
            temperature = 72,
            conditions = "Sunny",
            location = "San Francisco"
        }
    },
    stock_price = {
        returns = {
            symbol = "AAPL",
            price = 150.25,
            change = 2.5
        }
    },
    -- Agent mock for CI testing
    info_gatherer = {
        tool_calls = {
            {tool = "weather", args = {location = "San Francisco"}},
            {tool = "done", args = {reason = "The weather in San Francisco is 72°F and Sunny."}}
        },
        message = "I've gathered the weather information."
    }
}

-- Agent that uses mocked tools
info_gatherer = Agent {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = [[You are an information gathering assistant.

You have access to these tools:
- weather: Get current weather information
- stock_price: Get current stock price
- done: Signal completion

When asked for information, use the appropriate tools and then call done with a summary.]],
    tools = {"weather", "stock_price", "done"}
}

-- Main procedure

Procedure {
    input = {
            query = field.string{
                default = "weather",
                description = "What to query: weather or stock"
            }
    },
    output = {
            result = field.string{required = true, description = "Query result"},
            mocked = field.boolean{required = true, description = "Whether mocks were used"}
    },
    function(input)

    Log.info("Starting static mock demo", {query = input.query})

            -- Ask agent to get information
            local message
            if input.query == "stock" then
                message = "Please get the current stock price for AAPL and call done with the information."
            else
                message = "Please get the current weather in San Francisco and call done with the information."
            end

            -- Run agent
            info_gatherer({message = message})

            -- Wait for done
            local max_turns = 3
            local turn_count = 1

            while not done.called() and turn_count < max_turns do
                info_gatherer()
                turn_count = turn_count + 1
            end

            -- Get result
            local result = "No result"
            if done.called() then
                local call = done.last_call()
                if call and call.args then
                    local ok, reason = pcall(function() return call.args["reason"] end)
                    if ok and reason then
                        result = reason
                    end
                end
            end

            -- Check if mocks were used (they always are in this example)
            local mocked = Tool.called("weather") or Tool.called("stock_price")

            Log.info("Static mock demo complete", {
                result = result,
                mocked = mocked,
                turns = turn_count
            })

            return {
                result = result,
                mocked = mocked
            }

    -- BDD Specifications
    end
}

Specifications([[
Feature: Static Mocking
  Tools return the same value every time when mocked

  Scenario: Weather query uses static mock
    Given the procedure has started
    When the procedure runs
    Then the weather tool should be called
    And the done tool should be called
    And the output mocked should be True
    And the output result should exist
    And the procedure should complete successfully
]])
