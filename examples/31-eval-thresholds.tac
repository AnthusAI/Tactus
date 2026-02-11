-- Example: CI/CD Thresholds
-- This demonstrates quality gates for automated testing pipelines

-- Import completion tool from standard library
local done = require("tactus.tools.done")

greeter = Agent {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = [[You are a friendly greeter.

Generate a warm, personalized greeting for the given name.
Call the 'done' tool with your greeting.]],
    initial_message = "Generate a greeting for {name}",
    tools = {done}
}

Procedure {
    input = {
            name = field.string{required = true}
    },
    output = {
            greeting = field.string{required = true}
    },
    function(input)

    -- Have agent generate greeting
        greeter()

        -- Get result
        if done.called() then
            return {
                greeting = done.last_result() or "Task completed" or "Hello!"
            }
        end

        return {greeting = "No greeting generated"}

    -- BDD Specifications
    end
}

Specification([[
Feature: Greeting Generation with Thresholds

  Scenario: Agent generates greeting
    Given the procedure has started
    And the input name is "Alice"
    And the agent "greeter" responds with "I've generated a warm greeting."
    And the agent "greeter" calls tool "done" with args {"reason": "Hello! Welcome, it's great to see you!"}
    When the procedure runs
    Then the done tool should be called
    And the procedure should complete successfully
]])

-- Pydantic AI Evaluations with CI/CD Thresholds
-- Note: Evaluations framework is partially implemented.
-- Commented out until field.contains, field.llm_judge are available.
--[[
Evaluation({
    runs = 5,
    parallel = true,

    dataset = {
        {
            name = "greeting_alice",
            inputs = {name = "Alice"}
        },
        {
            name = "greeting_bob",
            inputs = {name = "Bob"}
        },
        {
            name = "greeting_charlie",
            inputs = {name = "Charlie"}
        }
    },

    evaluators = {
        -- Check greeting includes the name
        field.contains{},

        -- LLM judge for quality
        field.llm_judge{}
    },

    -- Quality gates for CI/CD
    thresholds = {
        min_success_rate = 0.80,  -- Require 80% success rate
        max_cost_per_run = 0.01,  -- Max $0.01 per run
        max_duration = 10.0,      -- Max 10 seconds per run
        max_tokens_per_run = 500  -- Max 500 tokens per run
    }
}
)
]]--
