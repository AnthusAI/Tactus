Feature: BDD Specifications (Gherkin)
  As a workflow developer
  I want to embed Gherkin BDD specifications in my procedures
  So that I can test workflow behavior with natural language specs

  Background:
  Given a Tactus validation environment

  Scenario: Simple Gherkin specification
  Given a Lua DSL file with content:
  """
  worker = Agent {
  provider = "openai",
  system_prompt = "Work",
  tools = {"done"}
  }

  main = Procedure "main" {
    function(input)
  Worker()
  return { result = "done" }
  end
  }

  Specification([[
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
  worker = Agent {
  provider = "openai",
  system_prompt = "Work",
  tools = {"done"}
  }
  
  main = Procedure "main" {
    function(input)
  Worker()
  return { result = "done" }
  end
  }
  
  Specification([[
  Feature: Multi Scenario
  
  Scenario: Procedure completes
  Given the procedure has started
  When the procedure runs
  Then the procedure should complete successfully
  
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
  worker = Agent {
  provider = "openai",
  system_prompt = "Work",
  tools = {"done"}
  }
  
  main = Procedure "main" {
    function(input)
  State.set("counter", 0)
  State.set("counter", 5)
  Worker()
  return { result = "done" }
  end
  }
  
  Specification([[
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
  worker = Agent {
  provider = "openai",
  system_prompt = "Work",
  tools = {"search", "done"}
  }

  main = Procedure "main" {
    function(input)
  Worker()
  return { result = "done" }
  end
  }

  Specification([[
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
  worker = Agent {
  provider = "openai",
  system_prompt = "Work",
  tools = {}
  }
  
  main = Procedure "main" {
    function(input)
  return { result = "done" }
  end
  }
  """
  When I validate the file
  Then validation should succeed
  And validation should have warnings



