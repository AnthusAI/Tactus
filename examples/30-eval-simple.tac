-- Simple Pydantic Evals Demo (No LLM calls)
-- Demonstrates evaluation without requiring OpenAI API

-- Simple procedure that just returns a greeting
procedure({
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
        },
        length = {
            type = "number",
            required = true
        }
    },
    state = {}
}, function()
    local greeting = "Hello, " .. input.name .. "!"

    return {
        greeting = greeting,
        length = string.len(greeting)
    }
end)

-- Pydantic Evals (output quality)
evaluations({
    dataset = {
        {
            name = "greet_alice",
            inputs = {name = "Alice"},
            expected_output = {
                greeting = "Hello, Alice!"
            }
        },
        {
            name = "greet_bob",
            inputs = {name = "Bob"},
            expected_output = {
                greeting = "Hello, Bob!"
            }
        },
        {
            name = "greet_charlie",
            inputs = {name = "Charlie"},
            expected_output = {
                greeting = "Hello, Charlie!"
            }
        }
    },
    
    evaluators = {
        -- Deterministic: Check exact match
        {
            type = "equals_expected",
            field = "greeting"
        },
        
        -- Deterministic: Check minimum length
        {
            type = "min_length",
            field = "greeting",
            value = 10
        },
        
        -- Deterministic: Check that greeting contains "Hello"
        {
            type = "contains",
            field = "greeting",
            value = "Hello"
        }
    },
    
    runs = 1,
    parallel = true
})
