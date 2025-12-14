Feature: Execution Settings (async, max_depth, max_turns)
  As a workflow developer
  I want to configure execution behavior
  So that I can control async execution, recursion limits, and agent turns

  Background:
    Given a Tactus validation environment

  Scenario: Async execution setting
    Given a Lua DSL file with content:
      """
      async(true)
      
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

  Scenario: Max depth setting
    Given a Lua DSL file with content:
      """
      max_depth(10)
      
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

  Scenario: Max turns setting
    Given a Lua DSL file with content:
      """
      max_turns(100)
      
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

  Scenario: All execution settings combined
    Given a Lua DSL file with content:
      """
      async(true)
      max_depth(5)
      max_turns(50)
      
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

  Scenario: Default execution settings
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
