-- Example: Comprehensive Evaluation Demo
-- This demonstrates all evaluation features:
-- - External dataset loading
-- - Trace inspection
-- - Advanced evaluators (regex, JSON schema, range)
-- - CI/CD thresholds

agent("contact_formatter", {
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
})

procedure({
    input = {
        raw_contact = {
            type = "string",
            required = true
        }
    },
    output = {
        phone = {
            type = "string",
            required = false
        },
        email = {
            type = "string",
            required = false
        },
        score = {
            type = "number",
            required = false
        },
        formatted = {
            type = "boolean",
            required = true
        }
    },
    state = {
        formatting_started = {
            type = "boolean",
            default = false,
            description = "Formatting has started"
        }
    }
}, function()
    State.set("formatting_started", true)
    
    -- Have agent format the contact
    ContactFormatter.turn()
    
    -- Extract result
    if Tool.called("done") then
        local result = Tool.last_call("done").args.reason or "{}"
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
end)

-- BDD Specifications
specifications([[
Feature: Contact Formatting with Comprehensive Evaluation

  Scenario: Agent formats contact information
    Given the procedure has started
    When the procedure runs with raw contact data
    Then the done tool should be called
    And the output should contain formatted phone and email
    And the procedure should complete successfully
]])

-- Pydantic AI Evaluations - Comprehensive Demo
evaluations({
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
        -- Regex: Validate phone format
        {
            type = "regex",
            field = "phone",
            value = "\\(\\d{3}\\) \\d{3}-\\d{4}"
        },
        
        -- Regex: Validate email format
        {
            type = "regex",
            field = "email",
            value = "[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}"
        },
        
        -- Range: Validate score
        {
            type = "range",
            field = "score",
            value = {min = 0, max = 100}
        },
        
        -- Trace: Verify done tool was called
        {
            type = "tool_called",
            value = "done",
            min_value = 1
        },
        
        -- Trace: Verify agent took reasonable turns
        {
            type = "agent_turns",
            field = "contact_formatter",
            min_value = 1,
            max_value = 3
        },
        
        -- Trace: Verify state was set
        {
            type = "state_check",
            field = "formatting_complete",
            value = true
        },
        
        -- LLM Judge: Overall quality
        {
            type = "llm_judge",
            rubric = [[
Score 1.0 if:
- Contact information is properly formatted
- Phone and email are valid
- Score is reasonable
- Agent completed the task efficiently

Score 0.0 otherwise.
            ]],
            model = "openai:gpt-4o-mini"
        }
    },
    
    -- CI/CD Quality Gates
    thresholds = {
        min_success_rate = 0.85,  -- Require 85% success
        max_cost_per_run = 0.02,  -- Max $0.02 per run
        max_duration = 15.0,      -- Max 15 seconds
        max_tokens_per_run = 1000 -- Max 1000 tokens
    }
})
