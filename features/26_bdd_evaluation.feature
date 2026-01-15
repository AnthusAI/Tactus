Feature: BDD Evaluation Configuration
  As a workflow developer
  I want to configure evaluation parameters for my BDD tests
  So that I can control test execution (runs, parallelism, etc.)

  Background:
  Given a Tactus validation environment

  Scenario: Basic evaluation configuration
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
  Scenario: Works
  Given the procedure has started
  When the procedure runs
  Then the procedure should complete successfully
  ]])
  
  Evaluation {
  runs = 10,
  parallel = true
  }
  """
  When I validate the file
  Then validation should succeed

  Scenario: Evaluation with custom runs
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
  Feature: Test
  Scenario: Works
  Given the procedure has started
  When the procedure runs
  Then the procedure should complete successfully
  ]])
  
  Evaluation {
  runs = 50
  }
  """
  When I validate the file
  Then validation should succeed

  Scenario: Evaluation with parallel disabled
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
  Feature: Test
  Scenario: Works
  Given the procedure has started
  When the procedure runs
  Then the procedure should complete successfully
  ]])
  
  Evaluation {
  runs = 5,
  parallel = false
  }
  """
  When I validate the file
  Then validation should succeed

  Scenario: Procedure without evaluation config
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
  Feature: Test
  Scenario: Works
  Given the procedure has started
  When the procedure runs
  Then the procedure should complete successfully
  ]])
  """
  When I validate the file
  Then validation should succeed
