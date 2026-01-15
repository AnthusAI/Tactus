Feature: BDD Custom Step Definitions
  As a workflow developer
  I want to define custom Gherkin step implementations
  So that I can test domain-specific workflow behavior

  Background:
  Given a Tactus validation environment

  Scenario: Custom step definition
  Given a Lua DSL file with content:
  """
  worker = Agent {
    provider = "openai",
    system_prompt = "Work",
    tools = {}
  }

  main = Procedure "main" {
    function(input)
      State.set("custom_value", 42)
      local result = Agent("worker")({query = "work"})
      return { result = "done" }
    end
  }

  Step("the custom value is correct", function(context)
    local value = State.get("custom_value")
    assert(value == 42, "Expected 42, got " .. tostring(value))
  end)

  Specification([[
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
  analyzer = Agent {
    provider = "openai",
    system_prompt = "Analyze",
    tools = {}
  }

  main = Procedure "main" {
    function(input)
      State.set("x", 10)
      State.set("y", 20)
      State.set("z", 30)
      return { result = "done" }
    end
  }

  Step("x equals 10", function(context)
    assert(State.get("x") == 10)
  end)

  Step("y equals 20", function(context)
    assert(State.get("y") == 20)
  end)

  Specification([[
    Feature: Multiple Steps
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
  analyzer = Agent {
    provider = "openai",
    system_prompt = "Analyze",
    tools = {}
  }

  main = Procedure "main" {
    function(input)
      State.set("items", {"a", "b", "c"})
      local result = Agent("analyzer")({task = "analyze"})
      return { result = "validated" }
    end
  }

  Step("the items list has correct format", function(context)
    local items = State.get("items")
    assert(items ~= nil, "Items should exist")
    assert(#items == 3, "Should have 3 items")
    assert(items[1] == "a", "First item should be 'a'")
  end)

  Specification([[
    Feature: Complex Custom Steps
    Scenario: List validation works
      Given the procedure has started
      When the procedure runs
      Then the items list has correct format
  ]])
  """
  When I validate the file
  Then validation should succeed
