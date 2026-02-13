-- Model Cost Tracking Example
--
-- Demonstrates accessing cost information from Model predictions in Lua.
-- Shows per-prediction costs and cumulative statistics.

Procedure {
    input = {
        texts = field.list{required = true, description = "List of texts to classify"}
    },
    output = {
        results = field.list{required = true, description = "Classification results"},
        total_cost = field.number{required = true, description = "Total cost"},
        avg_latency = field.number{required = true, description = "Average latency in ms"}
    },
    function(input)

    -- LLM Model with cost tracking
    local llm_classifier = Model "llm_classifier" {
        type = "llm",
        model = "openai/gpt-4o-mini",
        system_prompt = "Classify sentiment as positive, negative, or neutral. Return JSON: {\"label\": string}",
        input = { text = "string" },
        output = { label = "string" },
        temperature = 0.0,
        retries = 2,
    }

    -- HTTP Model with per-call cost tracking
    local http_classifier = Model "http_classifier" {
        type = "http",
        endpoint = "https://api.example.com/classify",
        cost_per_call = 0.01,  -- Track $0.01 per call
        input = { text = "string" },
        output = { label = "string" },
    }

    local results = {}

    -- Process each text
    for i, text in ipairs(input.texts) do
        print("\n=== Processing text " .. i .. " ===")
        print("Input: " .. text)

        -- Use LLM classifier
        local result = llm_classifier({text = text})

        -- Access prediction output
        -- Can use either result.output.label or result.label (nested access)
        local label = result.output.label
        print("Classification: " .. label)

        -- Access per-prediction cost information
        if result.cost then
            print("\nPer-prediction costs:")

            -- Inference cost (dollars)
            if result.cost.inference_cost then
                print("  Cost: $" .. result.cost.inference_cost)
            end

            -- Timing
            if result.cost.compute_time_ms then
                print("  Latency: " .. result.cost.compute_time_ms .. " ms")
            end

            -- Token usage (LLM only)
            if result.cost.tokens_in then
                print("  Tokens: " .. (result.cost.tokens_in + result.cost.tokens_out))
                print("    Input: " .. result.cost.tokens_in)
                print("    Output: " .. result.cost.tokens_out)
            end
        end

        -- Access metadata
        if result.backend_type then
            print("  Backend: " .. result.backend_type)
        end

        table.insert(results, {text = text, label = label})
    end

    -- Access cumulative model statistics
    print("\n=== Model Statistics ===")
    print("Total predictions: " .. llm_classifier.prediction_count)
    print("Total cost: $" .. llm_classifier.total_cost)
    print("Average latency: " .. llm_classifier.avg_latency_ms .. " ms")

    -- Compare with HTTP classifier statistics
    if http_classifier.prediction_count > 0 then
        print("\nHTTP Classifier:")
        print("  Predictions: " .. http_classifier.prediction_count)
        print("  Total cost: $" .. http_classifier.total_cost)
        print("  Avg latency: " .. http_classifier.avg_latency_ms .. " ms")
    end

    return {
        results = results,
        total_cost = llm_classifier.total_cost,
        avg_latency = llm_classifier.avg_latency_ms
    }

    end
}

-- BDD Specification
Specification([[
Feature: Model Cost Tracking
  Background:
    Given the procedure has started

  Scenario: Track LLM classification costs
    Given the input texts are ["Great product!", "Terrible service"]
    When the procedure runs
    Then the procedure should complete successfully
    And the output results should have 2 items
    And the output total_cost should be greater than 0
    And the output avg_latency should be greater than 0

  Scenario: Access per-prediction cost details
    Given the input texts are ["Hello world"]
    When the procedure runs
    Then the procedure should complete successfully
    And the cost information should include tokens_in
    And the cost information should include tokens_out
    And the cost information should include inference_cost
]])
