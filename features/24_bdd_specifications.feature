Feature: BDD Specifications (Gherkin)
  As a workflow developer
  I want to embed Gherkin BDD specifications in my procedures
  So that I can test workflow behavior with natural language specs

  Background:
    Given a Tactus validation environment

  Scenario: Simple Gherkin specification
    Given a Lua DSL file with content:
      """
      agent("worker", {
        provider = "openai",
        system_prompt = "Work",
        tools = {"done"}
      })
      
      procedure(function()
        Worker.turn()
        return { result = "done" }
      end)
      
      specifications([[
      Feature: Basic Test
        Scenario: Worker completes task
          Given the procedure has started
          When the procedure runs
          Then the procedure should complete successfully
      ]])
      """
    When I validate the file
    Then validation should succeed

  Scenario: Multiple scenarios in specification
    Given a Lua DSL file with content:
      """
      agent("worker", {
        provider = "openai",
        system_prompt = "Work",
        tools = {"done"}
      })
      
      stages({"start", "working", "done"})
      
      procedure(function()
        Stage.set("start")
        Stage.set("working")
        Worker.turn()
        Stage.set("done")
        return { result = "done" }
      end)
      
      specifications([[
      Feature: Stage Management
      
        Scenario: Stages transition correctly
          Given the procedure has started
          When the procedure runs
          Then the stage should be done
          
        Scenario: Worker is called
          Given the procedure has started
          When the procedure runs
          Then the done tool should be called
      ]])
      """
    When I validate the file
    Then validation should succeed

  Scenario: Specification with state assertions
    Given a Lua DSL file with content:
      """
      agent("worker", {
        provider = "openai",
        system_prompt = "Work",
        tools = {"done"}
      })
      
      procedure(function()
        State.set("counter", 0)
        State.set("counter", 5)
        Worker.turn()
        return { result = "done" }
      end)
      
      specifications([[
      Feature: State Management
      
        Scenario: State is updated correctly
          Given the procedure has started
          When the procedure runs
          Then the state counter should be 5
          And the procedure should complete successfully
      ]])
      """
    When I validate the file
    Then validation should succeed

  Scenario: Specification with tool call assertions
    Given a Lua DSL file with content:
      """
      agent("worker", {
        provider = "openai",
        system_prompt = "Work",
        tools = {"search", "done"}
      })
      
      procedure(function()
        Worker.turn()
        return { result = "done" }
      end)
      
      specifications([[
      Feature: Tool Usage
      
        Scenario: Required tools are called
          Given the procedure has started
          When the procedure runs
          Then the done tool should be called
      ]])
      """
    When I validate the file
    Then validation should succeed

  Scenario: Procedure without specifications
    Given a Lua DSL file with content:
      """
      agent("worker", {
        provider = "openai",
        system_prompt = "Work",
        tools = {}
      })
      
      procedure(function()
        return { result = "done" }
      end)
      """
    When I validate the file
    Then validation should succeed
    And validation should have warnings






