-- Sub-Procedure Composition with Auto-Checkpointing
--
-- Demonstrates automatic checkpointing of sub-procedure calls.
-- Each Procedure.run() call is automatically checkpointed, making
-- complex workflows durable even when composed of multiple procedures.
--
-- This example shows a data processing pipeline composed of
-- multiple sub-procedures that transform and analyze data.

agent("analyst", {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = [[
You are a data analyst.

The processed data shows:
- Sum: {state.sum}
- Product: {state.product}
- Average: {state.average}

Provide a brief analysis of these statistics.
Call done when finished.
]],
    tools = {"done"}
})

procedure({
    input = {
        numbers = {
            type = "array",
            required = true,
            description = "Array of numbers to analyze"
        }
    },
    output = {
        sum = {
            type = "number",
            required = true,
            description = "Sum of all numbers"
        },
        product = {
            type = "number",
            required = true,
            description = "Product of all numbers"
        },
        average = {
            type = "number",
            required = true,
            description = "Average of all numbers"
        },
        analysis = {
            type = "string",
            required = true,
            description = "AI analysis of the data"
        }
    },
    state = {
        sum = {type = "number", default = 0},
        product = {type = "number", default = 1},
        average = {type = "number", default = 0}
    }
}, function()
    -- Step 1: Calculate sum (auto-checkpointed)
    local sum_result = Procedure.run("examples/helpers/sum.tac", {
        values = input.numbers
    })
    state.sum = sum_result.result or sum_result

    -- Step 2: Calculate product (auto-checkpointed)
    local product_result = Procedure.run("examples/helpers/product.tac", {
        values = input.numbers
    })
    state.product = product_result.result or product_result

    -- Step 3: Calculate average
    state.average = state.sum / #input.numbers

    -- Step 4: Get AI analysis (auto-checkpointed agent turn)
    Analyst.turn({})

    return {
        sum = state.sum,
        product = state.product,
        average = state.average,
        analysis = Analyst.output
    }
end)

-- BDD Specifications
specifications([[
Feature: Sub-Procedure Composition with Auto-Checkpointing
  As a workflow developer
  I want to compose multiple procedures together
  So that I can build complex workflows from simple, reusable components

  Scenario: Multi-step data processing pipeline
    Given the procedure has started
    And the input numbers is [5, 10, 15]
    When the sum sub-procedure executes
    Then the sum state should be 30
    When the product sub-procedure executes
    Then the product state should be 750
    When the average is calculated
    Then the average state should be 10
    When the Analyst agent analyzes the data
    Then the analysis output should exist

  Scenario: Sub-procedures are checkpointed for replay
    Given the procedure has started
    And the input numbers is [2, 4, 8]
    When all sub-procedures execute
    And each sub-procedure call is checkpointed
    Then the execution log should contain procedure_call entries
    And the output sum should be 14
    And the output product should be 64
    And the output average should be 4.67

  Scenario: Complex workflow is durable
    Given the procedure has started
    And the input numbers is [3, 7, 11]
    When the procedure executes to completion
    And the procedure is restarted from checkpoint
    Then all sub-procedure results should be replayed
    And the final output should match the original
]])
