-- Example Tactus procedure with BDD specifications
-- This demonstrates the Gherkin BDD testing integration

-- Parameters
parameter("topic", {
  type = "string",
  required = true,
  description = "The topic to research"
})

-- Outputs
output("findings", {
  type = "string",
  required = true,
  description = "Research findings summary"
})

-- Agent definition
agent("researcher", {
  provider = "openai",
  model = "gpt-4o-mini",
  system_prompt = "You are researching: {params.topic}. Use the search tool to find information, then call done when complete.",
  tools = {"search", "done"}
})

-- Stages
stages({"researching", "complete"})

-- Main procedure
procedure(function()
  Stage.set("researching")
  
  repeat
    Researcher.turn()
  until Tool.called("done") or Iterations.exceeded(10)
  
  Stage.set("complete")
  
  return {
    findings = "Research completed on " .. params.topic
  }
end)

-- BDD Specifications using Gherkin syntax
specifications([[
Feature: Research Task Completion
  As a user
  I want the agent to research topics effectively
  So that I get reliable results

  Scenario: Agent completes basic research
    Given the procedure has started
    When the researcher agent takes turns
    Then the search tool should be called at least once
    And the done tool should be called exactly once
    And the procedure should complete successfully

  Scenario: Agent progresses through stages correctly
    Given the procedure has started
    When the procedure runs
    Then the stage should transition from researching to complete
    And the total iterations should be less than 10

  Scenario: Agent handles parameters correctly
    Given the topic parameter is quantum computing
    When the procedure runs
    Then the procedure should complete successfully
]])

-- Custom step for advanced validation
step("the research quality is high", function()
  local findings = State.get("findings")
  assert(findings ~= nil, "Findings should exist")
  assert(#findings > 10, "Findings should have substantial content")
end)

-- Evaluation configuration
evaluation({
  runs = 10,
  parallel = true
})
