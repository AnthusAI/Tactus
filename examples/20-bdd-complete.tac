-- Comprehensive BDD Testing Example for Tactus
-- Demonstrates all major features of the BDD testing framework

local done = require("tactus.tools.done")

-- Agent
processor = Agent {
  provider = "openai",
  model = "gpt-4o-mini",
  system_prompt = "Process the task: {input.task}. Call done when finished.",
  initial_message = "Start processing",
  tools = {done},
}

-- Procedure with input and output defined inline

Procedure {
    input = {
            task = field.string{required = false, description = "Task to perform", default = "process data"},
            iterations = field.number{required = false, description = "Number of iterations", default = 3},
    },
    output = {
            status = field.string{required = true, description = "Final status"},
            count = field.number{required = true, description = "Items processed"},
	    },
	    function(input)

	    -- Setup phase
	      state.items_processed = 0
	      state.errors = 0

	      -- Processing phase
	      local target = input.iterations or 3
	      for i = 1, target do
	        state.items_processed = i

        -- Simulate some work
        if i % 2 == 0 then
          state.last_even = i
        end
      end

	      -- Agent processes result
	      processor()

	      -- Validation phase
	      local processed = state.items_processed
	      if processed >= target then
	        state.validation_passed = true
      else
        state.validation_passed = false
	        state.errors = 1
	      end

	      return {
	        status = "success",
	        count = state.items_processed
	      }

    -- BDD Specifications
    end
}

Specification([[
Feature: Comprehensive Workflow Testing
  Demonstrate all BDD testing capabilities

	  Scenario: Complete workflow execution
	    Given the procedure has started
	    And the agent "processor" responds with "Processing complete."
	    And the agent "processor" calls tool "done" with args {"reason": "Processing complete"}
	    When the procedure runs
	    Then the done tool should be called
	    And the state items_processed should be 3
	    And the state validation_passed should be True
	    And the procedure should complete successfully

  Scenario: State management
    Given the procedure has started
    When the procedure runs
    Then the state items_processed should be 3
    And the state errors should be 0
    And the state validation_passed should exist

  Scenario: Tool usage
    Given the procedure has started
    And the agent "processor" responds with "Processing complete."
    And the agent "processor" calls tool "done" with args {"reason": "Processing complete"}
    When the processor agent takes turn
    Then the done tool should be called exactly 1 time
    And the procedure should complete successfully

  Scenario: Iteration limits
    Given the procedure has started
    When the procedure runs
    Then the total iterations should be less than 20
]])

-- Custom step for advanced validation
Step("the processing was efficient", function(input)
  local processed = state.items_processed
  local errors = state.errors
  assert(processed > 0, "Should have processed items")
  assert(errors == 0, "Should have no errors")
end)

-- Evaluation configuration
Evaluation({
  runs = 10,
  parallel = true
})
