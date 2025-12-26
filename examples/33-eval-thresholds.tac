-- Example: CI/CD Thresholds
-- This demonstrates quality gates for automated testing pipelines

agent("greeter", {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = [[You are a friendly greeter.

Generate a warm, personalized greeting for the given name.
Call the 'done' tool with your greeting.]],
    initial_message = "Generate a greeting for {name}",
})

main = procedure("main", {
    input = {
        name = {
            type = "string",
            required = true
        }
    },
    output = {
        greeting = {
            type = "string",
            required = true
        }
    },
    state = {}
}, function()
    -- Have agent generate greeting
    Greeter.turn()
    
    -- Get result
    if Tool.called("done") then
        return {
            greeting = Tool.last_call("done").args.reason or "Hello!"
        }
    end
    
    return {greeting = "No greeting generated"}
end)

-- BDD Specifications
specifications([[
Feature: Greeting Generation with Thresholds

  Scenario: Agent generates greeting
    Given the procedure has started
    When the procedure runs
    Then the done tool should be called
    And the procedure should complete successfully
]])

-- Pydantic AI Evaluations with CI/CD Thresholds
evaluations({
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
        {
            type = "contains",
            field = "greeting",
            value = "Alice"  -- This will fail for Bob/Charlie, demonstrating threshold
        },
        
        -- LLM judge for quality
        {
            type = "llm_judge",
            rubric = [[
Score 1.0 if the greeting is warm, personalized, and includes the person's name.
Score 0.0 if the greeting is generic or missing the name.
            ]],
            model = "openai:gpt-4o-mini"
        }
    },
    
    -- Quality gates for CI/CD
    thresholds = {
        min_success_rate = 0.80,  -- Require 80% success rate
        max_cost_per_run = 0.01,  -- Max $0.01 per run
        max_duration = 10.0,      -- Max 10 seconds per run
        max_tokens_per_run = 500  -- Max 500 tokens per run
    }
})
