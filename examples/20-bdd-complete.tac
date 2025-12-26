-- Comprehensive BDD Testing Example for Tactus
-- Demonstrates all major features of the BDD testing framework

-- Agent
agent("processor", {
  provider = "openai",
  model = "gpt-4o-mini",
  system_prompt = "Process the task: {input.task}. Call done when finished.",
  initial_message = "Start processing",
})

-- Stages
stages({"setup", "processing", "validation", "complete"})

-- Procedure with input and output defined inline
main = procedure("main", {
    input = {
        task = {
            type = "string",
            required = false,
            default = "process data",
            description = "Task to perform"
        },
        iterations = {
            type = "number",
            required = false,
            default = 3,
            description = "Number of iterations"
        },
    },
    output = {
        status = {
            type = "string",
            required = true,
            description = "Final status"
        },
        count = {
            type = "number",
            required = true,
            description = "Items processed"
        },
    },
    state = {
        items_processed = {
            type = "number",
            default = 0,
            description = "Items processed counter"
        },
        errors = {
            type = "number",
            default = 0,
            description = "Error count"
        },
        validation_passed = {
            type = "boolean",
            default = false,
            description = "Validation result"
        },
        last_even = {
            type = "number",
            default = 0,
            description = "Last even number"
        }
    }
}, function()
  -- Setup phase
  Stage.set("setup")
  State.set("items_processed", 0)
  State.set("errors", 0)

  -- Processing phase
  Stage.set("processing")

  local target = input.iterations or 3
  for i = 1, target do
    State.set("items_processed", i)
    
    -- Simulate some work
    if i % 2 == 0 then
      State.set("last_even", i)
    end
  end
  
  -- Agent processes result
  Processor.turn()
  
  -- Validation phase
  Stage.set("validation")
  local processed = State.get("items_processed")
  if processed >= target then
    State.set("validation_passed", true)
  else
    State.set("validation_passed", false)
    State.set("errors", 1)
  end
  
  -- Complete
  Stage.set("complete")
  
  return {
    status = "success",
    count = State.get("items_processed")
  }
end)

-- BDD Specifications
specifications([[
Feature: Comprehensive Workflow Testing
  Demonstrate all BDD testing capabilities

  Scenario: Complete workflow execution
    Given the procedure has started
    When the procedure runs
    Then the done tool should be called
    And the stage should be complete
    And the state items_processed should be 3
    And the state validation_passed should be True
    And the procedure should complete successfully

  Scenario: Stage progression
    Given the procedure has started
    When the procedure runs
    Then the stage should transition from setup to processing
    And the stage should transition from processing to validation
    And the stage should transition from validation to complete

  Scenario: State management
    Given the procedure has started
    When the procedure runs
    Then the state items_processed should be 3
    And the state errors should be 0
    And the state validation_passed should exist

  Scenario: Tool usage
    Given the procedure has started
    When the processor agent takes turn
    Then the done tool should be called exactly 1 time
    And the procedure should complete successfully

  Scenario: Iteration limits
    Given the procedure has started
    When the procedure runs
    Then the total iterations should be less than 20
]])

-- Custom step for advanced validation
step("the processing was efficient", function()
  local processed = State.get("items_processed")
  local errors = State.get("errors")
  assert(processed > 0, "Should have processed items")
  assert(errors == 0, "Should have no errors")
end)

-- Evaluation configuration
evaluation({
  runs = 10,
  parallel = true
})

