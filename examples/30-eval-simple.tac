-- Simple Pydantic Evals Demo (No LLM calls)
-- Demonstrates evaluation without requiring OpenAI API

-- Simple procedure that just returns a greeting
Procedure {
    input = {
        name = field.string{required = true}
    },
    output = {
        greeting = field.string{required = true},
        length = field.number{required = true}
    },
    function(input)
        local greeting = "Hello, " .. input.name .. "!"

        return {
            greeting = greeting,
            length = string.len(greeting)
        }
    end
}

Specification([[
Feature: Simple eval procedure

  Scenario: Greets Alice
    Given the procedure has started
    And the input name is "Alice"
    When the procedure runs
    Then the output greeting should be "Hello, Alice!"
    And the output length should be 13
]])

-- Pydantic Evals (output quality)
Evaluation({
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
        field.equals_expected{},

        -- Deterministic: Check minimum length
        field.min_length{field = "greeting", value = 1},

        -- Deterministic: Check that greeting contains "Hello"
        field.contains{field = "greeting", value = "Hello"}
    },

    runs = 1,
    parallel = true
})
