-- Working example of Tactus procedure with BDD specifications
-- This example uses simple state manipulation and can be tested with mocked tools

-- Agent definition (will be mocked in tests)
agent("worker", {
  provider = "openai",
  model = "gpt-4o-mini",
  system_prompt = "You are a worker. Call the done tool when finished.",
})

-- Stages
stages({"initializing", "working", "complete"})

-- Procedure with input, output, and state defined inline
main = procedure("main", {
    input = {
        count = {
            type = "number",
            required = false,
            default = 3,
            description = "Number of iterations to perform"
        },
    },
    output = {
        result = {
            type = "string",
            required = true,
            description = "Final result message"
        },
    },
    state = {
        counter = {
            type = "number",
            default = 0,
            description = "Working counter"
        },
        items = {
            type = "array",
            default = {},
            description = "List of items"
        }
    }
}, function()
  -- Initialize
  Stage.set("initializing")

  -- Do work
  Stage.set("working")

  local target = input.count or 3
  for i = 1, target do
    State.set("counter", i)
    local items = State.get("items") or {}
    table.insert(items, "item_" .. i)
    State.set("items", items)
  end

  -- Simulate agent turn (will call done tool)
  Worker.turn()

  -- Complete
  Stage.set("complete")

  return {
    result = "Processed " .. State.get("counter") .. " items"
  }
end)

-- BDD Specifications
specifications([[
Feature: Simple Workflow Execution
  As a developer
  I want to test workflow behavior
  So that I can ensure reliability

  Scenario: Workflow completes successfully
    Given the procedure has started
    When the procedure runs
    Then the done tool should be called
    And the stage should transition from initializing to working
    And the stage should transition from working to complete
    And the state counter should be 3
    And the procedure should complete successfully

  Scenario: Workflow processes correct number of items
    Given the procedure has started
    When the procedure runs
    Then the state counter should be 3
    And the total iterations should be less than 10

  Scenario: Workflow uses correct stages
    Given the procedure has started
    When the procedure runs
    Then the stage should be complete
]])

-- Custom step for validating items
step("the items list has correct format", function()
  local items = State.get("items")
  assert(items ~= nil, "Items should exist")
  assert(#items == 3, "Should have 3 items")
  assert(items[1] == "item_1", "First item should be item_1")
end)

-- Evaluation configuration
evaluation({
  runs = 10,
  parallel = true
})


