Feature: BDD Custom Step Definitions
  As a workflow developer
  I want to define custom Gherkin step implementations
  So that I can test domain-specific workflow behavior

  Background:
    Given a Tactus validation environment

  Scenario: Custom step definition
    Given a Lua DSL file with content:
      """
      agent("worker", {
        provider = "openai",
        system_prompt = "Work",
        tools = {"done"}
      })
      
      procedure(function()
        State.set("custom_value", 42)
        Worker.turn()
        return { result = "done" }
      end)
      
      step("the custom value is correct", function()
        local value = State.get("custom_value")
        assert(value == 42, "Expected 42, got " .. tostring(value))
      end)
      
      specifications([[
      Feature: Custom Steps
        Scenario: Custom step works
          Given the procedure has started
          When the procedure runs
          Then the custom value is correct
      ]])
      """
    When I validate the file
    Then validation should succeed

  Scenario: Multiple custom steps
    Given a Lua DSL file with content:
      """
      agent("worker", {
        provider = "openai",
        system_prompt = "Work",
        tools = {"done"}
      })
      
      procedure(function()
        State.set("x", 10)
        State.set("y", 20)
        Worker.turn()
        return { result = "done" }
      end)
      
      step("x equals 10", function()
        assert(State.get("x") == 10)
      end)
      
      step("y equals 20", function()
        assert(State.get("y") == 20)
      end)
      
      specifications([[
      Feature: Multiple Custom Steps
        Scenario: All values are correct
          Given the procedure has started
          When the procedure runs
          Then x equals 10
          And y equals 20
      ]])
      """
    When I validate the file
    Then validation should succeed

  Scenario: Custom step with complex logic
    Given a Lua DSL file with content:
      """
      agent("worker", {
        provider = "openai",
        system_prompt = "Work",
        tools = {"done"}
      })
      
      procedure(function()
        State.set("items", {"a", "b", "c"})
        Worker.turn()
        return { result = "done" }
      end)
      
      step("the items list has correct format", function()
        local items = State.get("items")
        assert(items ~= nil, "Items should exist")
        assert(#items == 3, "Should have 3 items")
        assert(items[1] == "a", "First item should be 'a'")
      end)
      
      specifications([[
      Feature: Complex Custom Steps
        Scenario: List validation works
          Given the procedure has started
          When the procedure runs
          Then the items list has correct format
      ]])
      """
    When I validate the file
    Then validation should succeed






