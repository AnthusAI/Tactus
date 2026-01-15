-- Example: Comprehensive Evaluation Demo
-- This demonstrates all evaluation features:
-- - External dataset loading
-- - Trace inspection
-- - Advanced evaluators (regex, JSON schema, range)
-- - CI/CD thresholds

local done = require("tactus.tools.done")

-- Define a validate tool for this example
validate = Tool {
    description = "Validate contact information",
    input = {
        data = field.string{required = true, description = "Data to validate"}
    },
    function(args)
        return {valid = true, message = "Validated: " .. args.data}
    end
}

contact_formatter = Agent {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = [[You are a contact information formatter.

Given raw contact information, format it properly:
1. Extract and validate phone number
2. Extract and validate email
3. Assign a quality score (0-100)
4. Call 'done' with the formatted data

	Return JSON with: {phone, email, score}]],
    initial_message = "Format this contact: {raw_contact}",
    tools = {validate, done}
}

Procedure {
    input = {
            raw_contact = field.string{required = true}
    },
    output = {
            phone = field.string{required = false},
            email = field.string{required = false},
            score = field.number{required = false},
            formatted = field.boolean{required = true}
    },
    function(input)

    state.formatting_started = true

        -- Have agent format the contact
        contact_formatter()

        -- Extract result
        if done.called() then
            local result = done.last_result() or "Task completed" or "{}"
            state.formatting_complete = true

            -- Parse JSON result (simplified for example)
            return {
                phone = "(555) 123-4567",
                email = "contact@example.com",
                score = 85,
                formatted = true
            }
        end

        return {
            formatted = false
        }

    -- BDD Specifications
    end
}

Specification([[
Feature: Contact Formatting with Comprehensive Evaluation

  Scenario: Agent formats contact information
    Given the procedure has started
    And the input raw_contact is "John Doe, 555-123-4567"
    And the agent "contact_formatter" responds with "I've formatted the contact information."
    And the agent "contact_formatter" calls tool "validate" with args {"data": "John Doe contact"}
    And the agent "contact_formatter" calls tool "done" with args {"reason": "{phone: '(555) 123-4567', email: 'john@example.com', score: 85}"}
    When the procedure runs
    Then the done tool should be called
    And the output formatted should be True
    And the procedure should complete successfully
]])

-- Pydantic AI Evaluations - Comprehensive Demo
-- Note: Evaluations framework is partially implemented.
-- Commented out for now.
--[[
Evaluation({
    runs = 3,
    parallel = true,

    -- Load additional cases from external file
    dataset_file = "eval-with-dataset-file.jsonl",

    -- Plus inline cases
    dataset = {
        {
            name = "contact_john",
            inputs = {
                raw_contact = "John Doe, 555-123-4567, john@example.com"
            }
        }
    },

    evaluators = {
        -- Simple contains evaluator for phone
        {
            name = "has_phone",
            type = "contains",
            expected = "555"
        },

        -- Simple contains evaluator for email
        {
            name = "has_email",
            type = "contains",
            expected = "@"
        }
    },

    -- CI/CD Quality Gates
    thresholds = {
        min_success_rate = 0.85,  -- Require 85% success
        max_cost_per_run = 0.02,  -- Max $0.02 per run
        max_duration = 15.0,      -- Max 15 seconds
        max_tokens_per_run = 1000 -- Max 1000 tokens
    }
}
)
]]--
