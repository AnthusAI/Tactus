-- Pydantic Evals Demo
-- Demonstrates integration of Pydantic Evals with Tactus

-- Agent definition
Agent "greeter" {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = "You are a friendly greeter. Generate a warm greeting for the given name. Call the done tool with your greeting as the reason.",
    initial_message = "Generate a warm greeting",
}

-- Procedure

input {
        name = field.string{required = true, description = "Name to greet"}
    }

output {
        greeting = field.string{required = true, description = "The greeting message"}
    }

Log.info("Generating greeting", {name = input.name})
    
    -- Have agent generate greeting
    Agent("greeter").turn()
    
    -- Get greeting from done tool
    local greeting = "Hello!"
    if Tool.called("done") then
        greeting = Tool.last_result("done") or "Task completed" or "Hello!"
    end
    
    return {
        greeting = greeting
    }

-- BDD Specifications(workflow correctness)
Specifications([[
Feature: Greeting Generation
  Scenario: Agent generates greeting
    Given the procedure has started
    When the procedure runs
    Then the done tool should be called
    And the procedure should complete successfully
]])

-- Pydantic Evals (output quality)
Evaluations({
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
        field.contains_any{},
        
        -- Deterministic: Check minimum length
        field.min_length{},
        
        -- LLM-as-judge: Evaluate greeting quality
        field.llm_judge{}
    },
    
    -- Run each case once (increase for consistency measurement)
    runs = 1,
    parallel = true
}
)
