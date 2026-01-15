-- Working example of Tactus procedure with BDD specifications
-- This example uses simple state manipulation and can be tested with mocked tools

local done = require("tactus.tools.done")

-- Agent definition (will be mocked in tests)
worker = Agent {
  provider = "openai",
  model = "gpt-4o-mini",
  system_prompt = "You are a worker. Call the done tool when finished.",
  tools = {done},
}

-- Procedure with input, output, and state defined inline

Procedure {
    input = {
            count = field.number{required = false, description = "Number of iterations to perform", default = 3},
    },
    output = {
            result = field.string{required = true, description = "Final result message"},
	    },
	    function(input)

	    -- Initialize
	      local target = input.count or 3
	      for i = 1, target do
	        state.counter = i
        local items = state.items or {}
        table.insert(items, "item_" .. i)
        state.items = items
      end

	      -- Simulate agent turn (will call done tool)
	      worker()

	      return {
	        result = "Processed " .. state.counter .. " items"
	      }

    -- BDD Specifications
    end
}

Specification([[
Feature: Simple Workflow Execution
  As a developer
  I want to test workflow behavior
  So that I can ensure reliability

	  Scenario: Workflow completes successfully
	    Given the procedure has started
	    And the agent "worker" responds with "I have completed the work."
	    And the agent "worker" calls tool "done" with args {"reason": "Work completed"}
	    When the procedure runs
	    Then the done tool should be called
	    And the state counter should be 3
	    And the procedure should complete successfully

  Scenario: Workflow processes correct number of items
    Given the procedure has started
    When the procedure runs
    Then the state counter should be 3
    And the total iterations should be less than 10

]])

-- Custom step for validating items
Step("the items list has correct format", function(input)
  local items = state.items
  assert(items ~= nil, "Items should exist")
  assert(#items == 3, "Should have 3 items")
  assert(items[1] == "item_1", "First item should be item_1")
end)

-- Evaluation configuration
Evaluation({
  runs = 10,
  parallel = true
})
