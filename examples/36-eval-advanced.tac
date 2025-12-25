-- Example: Advanced Evaluator Types
-- This demonstrates regex, JSON schema, and numeric range evaluators

agent("formatter", {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = [[You are a helpful assistant that formats data.

When given a task, complete it and call the 'done' tool with your result.
Format your output according to the requirements.

IMPORTANT: Always call the done tool immediately with your formatted result.]],
    initial_message = "{task}",
    request_limit = 5
})

procedure({
    input = {
        task = {
            type = "string",
            required = true
        }
    },
    output = {
        result = {
            type = "string",
            required = true
        },
        score = {
            type = "number",
            required = false
        },
        data = {
            type = "object",
            required = false
        }
    },
    state = {}
}, function()
    -- Have agent complete the task
    Formatter.turn()
    
    -- Get result
    if Tool.called("done") then
        local output = Tool.last_call("done").args.reason or ""
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
end)

-- BDD Specifications
specifications([[
Feature: Advanced Evaluator Types

  Scenario: Agent formats output correctly
    Given the procedure has started
    When the procedure runs
    Then the done tool should be called
    And the procedure should complete successfully
]])

-- Pydantic AI Evaluations with Advanced Evaluators
evaluations({
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
        -- Regex: Check for the word "test"
        {
            type = "regex",
            field = "result",
            value = "test",
            case_sensitive = false
        },
        
        -- Numeric range: Check score is between 0-100
        {
            type = "range",
            field = "score",
            value = {min = 0, max = 100}
        },
        
        -- JSON Schema: Validate data structure
        {
            type = "json_schema",
            field = "data",
            value = {
                type = "object",
                properties = {
                    name = {type = "string"},
                    value = {type = "number"}
                },
                required = {"name", "value"}
            }
        }
    }
})
