-- Example: Advanced Evaluator Types
-- This demonstrates regex, JSON schema, and numeric range evaluators

local done = require("tactus.tools.done")

formatter = Agent {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = [[You are a helpful assistant that formats data.

When given a task, complete it and call the 'done' tool with your result.
Format your output according to the requirements.

    IMPORTANT: Always call the done tool immediately with your formatted result.]],
    initial_message = "{task}",
    tools = {done},
    request_limit = 5
}

Procedure {
    input = {
            task = field.string{required = true}
    },
    output = {
            result = field.string{required = true},
            score = field.number{required = false},
            data = field.object{required = false}
    },
    function(input)

    -- Have agent complete the task
        formatter()

        -- Get result
        if done.called() then
            local output = done.last_result() or "Task completed" or ""
            return {
                result = output,
                score = 85,  -- Mock score for testing
                data = {name = "test", value = 42}  -- Mock data for testing
            }
        end

        return {
            result = "Task not completed",
            score = 0
        }

    -- BDD Specifications
    end
}

Specification([[
Feature: Advanced Evaluator Types

  Scenario: Agent formats output correctly
    Given the procedure has started
    And the input task is "Return the word test"
    And the agent "formatter" responds with "I've formatted the data."
    And the agent "formatter" calls tool "done" with args {"reason": "test formatted result"}
    When the procedure runs
    Then the procedure should complete successfully
    And the output result should exist
]])

-- Pydantic AI Evaluations with Advanced Evaluators
Evaluation({
    runs = 2,
    parallel = true,
    
    dataset = {
        {
            name = "simple_format",
            inputs = {
                task = "Return the word 'test' in your result"
            }
        }
    },
    
    evaluators = {
        -- Simple string contains evaluator
        {
            name = "contains_test",
            type = "contains",
            expected = "test"
        }
    }
}
)
