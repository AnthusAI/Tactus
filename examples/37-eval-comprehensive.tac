-- Example: Comprehensive Evaluation Demo
-- This demonstrates all evaluation features:
-- - External dataset loading
-- - Trace inspection
-- - Advanced evaluators (regex, JSON schema, range)
-- - CI/CD thresholds

Agent "contact_formatter" {
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
    toolsets = {"validate"}
}

input {
        raw_contact = field.string{required = true}
    }

output {
        phone = field.string{required = false},
        email = field.string{required = false},
        score = field.number{required = false},
        formatted = field.boolean{required = true}
    }

State.set("formatting_started", true)
    
    -- Have agent format the contact
    Agent("contact_formatter").turn()
    
    -- Extract result
    if Tool.called("done") then
        local result = Tool.last_result("done") or "Task completed" or "{}"
        State.set("formatting_complete", true)
        
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
Specifications([[
Feature: Contact Formatting with Comprehensive Evaluation

  Scenario: Agent formats contact information
    Given the procedure has started
    When the procedure runs with raw contact data
    Then the done tool should be called
    And the output should contain formatted phone and email
    And the procedure should complete successfully
]])

-- Pydantic AI Evaluations - Comprehensive Demo
Evaluations({
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
