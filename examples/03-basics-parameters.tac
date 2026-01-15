-- Parameters Example
-- Demonstrates accessing parameters and using them in procedure logic

-- Agents (defined at top level - reusable across procedures)
worker = Agent {
    provider = "openai",
    system_prompt = "A worker agent",
    initial_message = "Processing task",
    tools = {}
}

-- Procedure with input and output defined inline
Procedure {
    input = {
        task = field.string{description = "The task name to process", default = "default task"},
        count = field.number{description = "Number of iterations to perform", default = 3},
    },
    output = {
        result = field.string{required = true, description = "Summary of the completed work"},
    },
    function(input)
        -- Access input
        local task = input.task
        local count = input.count

        Log.info("Running task", {task = task, count = count})

        -- Use parameters in workflow
        state.iterations = 0
        for i = 1, count do
          State.increment("iterations")
          Log.info("Iteration", {number = i, task = task})
        end

        local final_iterations = state.iterations

        return {
          result = "Completed " .. task .. " with " .. final_iterations .. " iterations"
        }
    end
}

-- BDD Specifications
Specification([[
Feature: Parameter Usage
  Demonstrate parameter access and usage in workflows

  Scenario: Parameters are used correctly
    Given the procedure has started
    When the procedure runs
    Then the procedure should complete successfully
    And the state iterations should be 3
    And the output result should exist
]])
