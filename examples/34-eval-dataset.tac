-- Example: External Dataset File Loading
-- This demonstrates loading evaluation cases from an external JSONL file
-- instead of defining them inline in the .tac file.

Agent("completer", {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = [[You are a helpful assistant that completes tasks.

When you complete a task, call the 'done' tool with your result.
Always start your response with "TASK_COMPLETE: " followed by your actual work.]],
    initial_message = "{task}\n\nPlease complete this task now.",
})

Procedure "main" {
    input = {
        task = field.string{required = true}
    },
    output = {
        output = field.string{required = true},
        completed = field.boolean{required = true}
    },
    function(input)
    -- Have agent complete the task
    Agent("completer").turn()
    
    -- Get result
    local output = "Task not completed"
    local completed = false
    
    if Tool.called("done") then
        output = Tool.last_result("done") or "Task completed" or "No output"
        completed = true
    end
    
    return {
        output = output,
        completed = completed
    }
end
}

-- BDD Specifications
Specifications([[
Feature: Task Completion with External Dataset

  Scenario: Agent completes task from external dataset
    Given the procedure has started
    When the procedure runs
    Then the done tool should be called
    And the procedure should complete successfully
]])

-- Pydantic AI Evaluations with External Dataset
Evaluations({
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
        field.contains{},
        
        -- Use LLM judge for quality
        field.llm_judge{}
    }
}
)
