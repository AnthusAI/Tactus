-- Example: CI/CD Thresholds
-- This demonstrates quality gates for automated testing pipelines

Agent "greeter" {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = [[You are a friendly greeter.

Generate a warm, personalized greeting for the given name.
Call the 'done' tool with your greeting.]],
    initial_message = "Generate a greeting for {name}",
}

input {
        name = field.string{required = true}
    }

output {
        greeting = field.string{required = true}
    }

-- Have agent generate greeting
    Agent("greeter").turn()
    
    -- Get result
    if Tool.called("done") then
        return {
            greeting = Tool.last_result("done") or "Task completed" or "Hello!"
        }
    end
    
    return {greeting = "No greeting generated"}

-- BDD Specifications
Specifications([[
Feature: Greeting Generation with Thresholds

  Scenario: Agent generates greeting
    Given the procedure has started
    When the procedure runs
    Then the done tool should be called
    And the procedure should complete successfully
]])

-- Pydantic AI Evaluations with CI/CD Thresholds
Evaluations({
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
