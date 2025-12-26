-- Parameters Example
-- Demonstrates accessing parameters and using them in procedure logic

-- Agents (defined at top level - reusable across procedures)
agent("worker", {
    provider = "openai",
    system_prompt = "A worker agent",
    initial_message = "Processing task",
    toolsets = {},
})

-- Procedure with input and output defined inline
main = procedure("main", {
    input = {
        task = {
            type = "string",
            default = "default task",
            description = "The task name to process",
        },
        count = {
            type = "number",
            default = 3,
            description = "Number of iterations to perform",
        },
    },
    output = {
        result = {
            type = "string",
            required = true,
            description = "Summary of the completed work",
        },
    },
    state = {
        iterations = {
            type = "number",
            default = 0,
            description = "Counter for iterations"
        }
    }
}, function()
    -- Access input
    local task = input.task
    local count = input.count

    Log.info("Running task", {task = task, count = count})

    -- Use parameters in workflow
    State.set("iterations", 0)
    for i = 1, count do
      State.increment("iterations")
      Log.info("Iteration", {number = i, task = task})
    end

    local final_iterations = State.get("iterations")

    return {
      result = "Completed " .. task .. " with " .. final_iterations .. " iterations"
    }
end)

-- BDD Specifications
specifications([[
Feature: Parameter Usage
  Demonstrate parameter access and usage in workflows

  Scenario: Parameters are used correctly
    Given the procedure has started
    When the procedure runs
    Then the procedure should complete successfully
    And the state iterations should be 3
    And the output result should exist
]])
