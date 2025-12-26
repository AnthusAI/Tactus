Feature: BDD Evaluation Configuration
  As a workflow developer
  I want to configure evaluation parameters for my BDD tests
  So that I can control test execution (runs, parallelism, etc.)

  Background:
    Given a Tactus validation environment

  Scenario: Basic evaluation configuration
    Given a Lua DSL file with content:
      """
      agent("worker", {
        provider = "openai",
        system_prompt = "Work",
        tools = {"done"}
      })

      main = procedure("main", function()
        Worker.turn()
        return { result = "done" }
      end)

      specifications([[
      Feature: Basic Test
        Scenario: Works
          Given the procedure has started
          When the procedure runs
          Then the procedure should complete successfully
      ]])
      
      evaluation({
        runs = 10,
        parallel = true
      })
      """
    When I validate the file
    Then validation should succeed

  Scenario: Evaluation with custom runs
    Given a Lua DSL file with content:
      """
      agent("worker", {
        provider = "openai",
        system_prompt = "Work",
        tools = {"done"}
      })

      main = procedure("main", function()
        Worker.turn()
        return { result = "done" }
      end)

      specifications([[
      Feature: Test
        Scenario: Works
          Given the procedure has started
          When the procedure runs
          Then the procedure should complete successfully
      ]])
      
      evaluation({
        runs = 50
      })
      """
    When I validate the file
    Then validation should succeed

  Scenario: Evaluation with parallel disabled
    Given a Lua DSL file with content:
      """
      agent("worker", {
        provider = "openai",
        system_prompt = "Work",
        tools = {"done"}
      })

      main = procedure("main", function()
        Worker.turn()
        return { result = "done" }
      end)

      specifications([[
      Feature: Test
        Scenario: Works
          Given the procedure has started
          When the procedure runs
          Then the procedure should complete successfully
      ]])
      
      evaluation({
        runs = 5,
        parallel = false
      })
      """
    When I validate the file
    Then validation should succeed

  Scenario: Procedure without evaluation config
    Given a Lua DSL file with content:
      """
      agent("worker", {
        provider = "openai",
        system_prompt = "Work",
        tools = {"done"}
      })

      main = procedure("main", function()
        Worker.turn()
        return { result = "done" }
      end)

      specifications([[
      Feature: Test
        Scenario: Works
          Given the procedure has started
          When the procedure runs
          Then the procedure should complete successfully
      ]])
      """
    When I validate the file
    Then validation should succeed
