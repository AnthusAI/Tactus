-- Sub-Procedure Composition with Auto-Checkpointing
--
-- Demonstrates automatic checkpointing of sub-procedure calls.
-- Each Procedure.run() call is automatically checkpointed, making
-- complex workflows durable even when composed of multiple procedures.
--
-- This example shows a data processing pipeline composed of
-- multiple sub-procedures that transform and analyze data.

-- Import the done tool from standard library
local done = require("tactus.tools.done")

analyst = Agent {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = [[
You are a data analyst.

The processed data shows:
- Sum: {State.sum}
- Product: {State.product}
- Average: {State.average}

Provide a brief analysis of these statistics.
	Call done when finished.
	]],
    tools = {done}
}

Procedure {
    input = {
            numbers = field.array{required = true, description = "Array of numbers to analyze"}
    },
    output = {
            sum = field.number{required = true, description = "Sum of all numbers"},
            product = field.number{required = true, description = "Product of all numbers"},
            average = field.number{required = true, description = "Average of all numbers"},
            analysis = field.string{required = true, description = "AI analysis of the data"}
    },
    function(input)

    -- Step 1: Calculate sum (auto-checkpointed)
        local sum_result = Procedure.run("examples/helpers/sum.tac", {
            values = input.numbers
        })
        State.sum = sum_result.result or sum_result

        -- Step 2: Calculate product (auto-checkpointed)
        local product_result = Procedure.run("examples/helpers/product.tac", {
            values = input.numbers
        })
        State.product = product_result.result or product_result

        -- Step 3: Calculate average
        State.average = State.sum / #input.numbers

        -- Step 4: Get AI analysis (auto-checkpointed agent turn)
        analyst({})

        return {
            sum = State.sum,
            product = State.product,
            average = State.average,
            analysis = analyst.output
        }

    -- BDD Specifications
    end
}

Specification([[
Feature: Sub-Procedure Composition with Auto-Checkpointing
  As a workflow developer
  I want to compose multiple procedures together
  So that I can build complex workflows from simple, reusable components

  Scenario: Multi-step data processing pipeline
    Given the procedure has started
    And the input numbers is [5, 10, 15]
    And the agent "analyst" responds with "I've analyzed the data statistics."
    And the agent "analyst" calls tool "done" with args {"reason": "The data shows a sum of 30, product of 750, and average of 10. This indicates a balanced distribution."}
    When the procedure runs
    Then the done tool should be called
    And the output sum should exist
    And the output product should exist
    And the output average should exist
    And the output analysis should exist
    And the procedure should complete successfully
]])
