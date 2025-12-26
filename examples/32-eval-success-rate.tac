-- Example: Measuring Success Rate with Pydantic AI Evals
-- This demonstrates how to evaluate the percentage of times a procedure
-- successfully completes a task by running it multiple times.

-- Agent definition  
agent("completer", {
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
})

-- Procedure
main = procedure("main", {
    input = {
        task = {
            type = "string",
            required = true,
            description = "The task to complete"
        }
    },
    output = {
        output = {
            type = "string",
            required = true,
            description = "The task completion output"
        },
        completed = {
            type = "boolean",
            required = true,
            description = "Whether task was completed"
        }
    },
    state = {}
}, function()
    Log.info("Starting task", {task = input.task})
    
    -- Have agent complete the task
    -- The initial_message template will inject the task parameter
    Completer.turn()
    
    -- Get result from done tool
    local output = "Task not completed - agent did not call done tool"
    local completed = false
    
    if Tool.called("done") then
        output = Tool.last_call("done").args.reason or "TASK_COMPLETE: (no output provided)"
        completed = true
        Log.info("Task completed", {output = output})
    else
        Log.warn("Agent did not complete task")
    end
    
    return {
        output = output,
        completed = completed
    }
end)

-- BDD Specifications (workflow correctness)
specifications([[
Feature: Task Completion
  Scenario: Agent completes simple task
    Given the procedure has started
    When the procedure runs
    Then the done tool should be called
    And the procedure should complete successfully
]])

-- Pydantic AI Evaluations for success rate measurement
evaluations({
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
        {
            type = "contains",
            field = "output",
            value = "TASK_COMPLETE"
        },
        
        -- Use LLM to judge if task was actually completed successfully
        {
            type = "llm_judge",
            rubric = [[
Evaluate whether the agent successfully completed the given task:
- Did it produce a relevant, complete response?
- Did it call the 'done' tool appropriately?
- Is the output quality acceptable?

Score 1.0 if the task was completed successfully, 0.0 if it failed or was incomplete.
            ]],
            model = "openai:gpt-4o-mini"
        }
    }
})
