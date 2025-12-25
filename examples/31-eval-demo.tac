-- Pydantic Evals Demo
-- Demonstrates integration of Pydantic Evals with Tactus

-- Agent definition
agent("greeter", {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = "You are a friendly greeter. Generate a warm greeting for the given name. Call the done tool with your greeting as the reason.",
    initial_message = "Generate a warm greeting",
})

-- Procedure
procedure({
    input = {
        name = {
            type = "string",
            required = true,
            description = "Name to greet"
        }
    },
    output = {
        greeting = {
            type = "string",
            required = true,
            description = "The greeting message"
        }
    },
    state = {}
}, function()
    Log.info("Generating greeting", {name = input.name})
    
    -- Have agent generate greeting
    Greeter.turn()
    
    -- Get greeting from done tool
    local greeting = "Hello!"
    if Tool.called("done") then
        greeting = Tool.last_call("done").args.reason or "Hello!"
    end
    
    return {
        greeting = greeting
    }
end)

-- BDD Specifications (workflow correctness)
specifications([[
Feature: Greeting Generation
  Scenario: Agent generates greeting
    Given the procedure has started
    When the procedure runs
    Then the done tool should be called
    And the procedure should complete successfully
]])

-- Pydantic Evals (output quality)
evaluations({
    dataset = {
        {
            name = "greet_alice",
            inputs = {name = "Alice"},
            expected_output = {
                contains_name = "Alice"
            }
        },
        {
            name = "greet_bob",
            inputs = {name = "Bob"},
            expected_output = {
                contains_name = "Bob"
            }
        }
    },
    
    evaluators = {
        -- Deterministic: Check greeting contains the name
        {
            type = "contains_any",
            field = "greeting",
            check_expected = "contains_name"
        },
        
        -- Deterministic: Check minimum length
        {
            type = "min_length",
            field = "greeting",
            value = 5
        },
        
        -- LLM-as-judge: Evaluate greeting quality
        {
            type = "llm_judge",
            rubric = [[
                Evaluate the greeting quality:
                - Is it warm and friendly?
                - Is it appropriate and professional?
                - Does it feel personalized?
                
                Score 0.0 (poor) to 1.0 (excellent)
            ]],
            model = "openai:gpt-4o-mini"
        }
    },
    
    -- Run each case once (increase for consistency measurement)
    runs = 1,
    parallel = true
})
