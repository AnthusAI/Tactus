-- Example: Measuring Success Rate with Pydantic AI Evals
-- This demonstrates how to evaluate the percentage of times a procedure
-- successfully completes a task by running it multiple times.

-- Import completion tool from standard library
local done = require("tactus.tools.done")

-- Agent definition
completer = Agent {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = [[You are a helpful assistant that completes tasks.

CRITICAL INSTRUCTIONS:
1. You MUST actually DO the task - write the greeting/haiku/list, don't just acknowledge it
2. You MUST call the 'done' tool with your result
3. You MUST start your done message with exactly "TASK_COMPLETE: " (including the colon and space)
4. After "TASK_COMPLETE: " put your actual work

CORRECT example for greeting Alice:
done(reason="TASK_COMPLETE: Hello Alice! It's wonderful to meet you. I hope you're having a great day!")

WRONG examples:
- done(reason="Task completed")  ← No actual work!
- done(reason="Hello Alice!")  ← Missing TASK_COMPLETE prefix!

Always follow this format exactly.]],
    initial_message = "{task}\n\nPlease complete this task now and call the done tool with your result.",
    tools = {done}
}

-- Procedure

Procedure {
    input = {
            task = field.string{required = true, description = "The task to complete"}
    },
    output = {
            output = field.string{required = true, description = "The task completion output"},
            completed = field.boolean{required = true, description = "Whether task was completed"}
    },
    function(input)

    Log.info("Starting task", {task = input.task})

        -- Have agent complete the task
        -- The initial_message template will inject the task parameter
        completer()

        -- Get result from done tool
        local output = "Task not completed - agent did not call done tool"
        local completed = false

        if done.called() then
            output = done.last_result() or "Task completed" or "TASK_COMPLETE: (no output provided)"
            completed = true
            Log.info("Task completed", {output = output})
        else
            Log.warn("Agent did not complete task")
        end

        return {
            output = output,
            completed = completed
        }

    -- BDD Specifications(workflow correctness)
    end
}

Specification([[
Feature: Task Completion
  Scenario: Agent completes simple task
    Given the procedure has started
    And the input task is "Say hello to the user"
    And the agent "completer" responds with "I've completed the task."
    And the agent "completer" calls tool "done" with args {"reason": "TASK_COMPLETE: Hello Alice! It's wonderful to meet you!"}
    When the procedure runs
    Then the done tool should be called
    And the procedure should complete successfully
]])

-- Pydantic AI Evaluations for success rate measurement
-- Note: Evaluations framework is partially implemented.
-- Commented out until field.contains, field.llm_judge are available.
--[[
Evaluation({
    -- Run each test case 3 times to measure success rate (reduced for testing)
    runs = 3,
    parallel = true,

    dataset = {
        {
            name = "simple_greeting",
            inputs = {
                task = "Generate a friendly greeting for a user named Alice"
            }
        },
        {
            name = "haiku_generation",
            inputs = {
                task = "Write a haiku about artificial intelligence"
            }
        },
        {
            name = "list_creation",
            inputs = {
                task = "Create a list of 3 benefits of automated testing"
            }
        }
    },

    evaluators = {
        -- Check if output contains the success marker
        field.contains{},

        -- Use LLM to judge if task was actually completed successfully
        field.llm_judge{}
    }
}
)
]]--
