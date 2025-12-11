-- Migrated from .tyml format to .tactus.lua

name("with_parameters")
version("1.0.0")
description("Demonstrates parameter usage in Tactus workflows")

-- Parameters
parameter("task", {
    type = "string",
    default = "default task",
    description = "The task name to process",
})
parameter("count", {
    type = "number",
    default = 3,
    description = "Number of iterations to perform",
})

-- Outputs
output("result", {
    type = "string",
    required = true,
    description = "Summary of the completed work",
})

-- Agents
agent("worker", {
    provider = "openai",
    system_prompt = "A worker agent",
    initial_message = "Processing task",
    tools = {},
})

-- Procedure
procedure(function()
    -- Parameters Example
    -- Demonstrates accessing parameters and using them in procedure logic

    -- Access parameters
    local task = params.task
    local count = params.count

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
