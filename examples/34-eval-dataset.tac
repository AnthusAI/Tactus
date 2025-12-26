-- Example: External Dataset File Loading
-- This demonstrates loading evaluation cases from an external JSONL file
-- instead of defining them inline in the .tac file.

agent("completer", {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = [[You are a helpful assistant that completes tasks.

When you complete a task, call the 'done' tool with your result.
Always start your response with "TASK_COMPLETE: " followed by your actual work.]],
    initial_message = "{task}\n\nPlease complete this task now.",
})

main = procedure("main", {
    input = {
        task = {
            type = "string",
            required = true
        }
    },
    output = {
        output = {
            type = "string",
            required = true
        },
        completed = {
            type = "boolean",
            required = true
        }
    },
    state = {}
}, function()
    -- Have agent complete the task
    Completer.turn()
    
    -- Get result
    local output = "Task not completed"
    local completed = false
    
    if Tool.called("done") then
        output = Tool.last_call("done").args.reason or "No output"
        completed = true
    end
    
    return {
        output = output,
        completed = completed
    }
end)

-- BDD Specifications
specifications([[
Feature: Task Completion with External Dataset

  Scenario: Agent completes task from external dataset
    Given the procedure has started
    When the procedure runs
    Then the done tool should be called
    And the procedure should complete successfully
]])

-- Pydantic AI Evaluations with External Dataset
evaluations({
    runs = 2,
    parallel = true,
    
    -- Load cases from external JSONL file
    dataset_file = "eval-with-dataset-file.jsonl",
    
    -- Can also include inline cases (these will be added to file cases)
    dataset = {
        {
            name = "inline_task",
            inputs = {
                task = "Say hello to the world"
            },
            metadata = {
                category = "inline"
            }
        }
    },
    
    evaluators = {
        -- Check for completion marker
        {
            type = "contains",
            field = "output",
            value = "TASK_COMPLETE"
        },
        
        -- Use LLM judge for quality
        {
            type = "llm_judge",
            rubric = [[
Score 1.0 if the agent successfully completed the task with appropriate output.
Score 0.0 if the task was not completed or output is inadequate.
            ]],
            model = "openai:gpt-4o-mini"
        }
    }
})
