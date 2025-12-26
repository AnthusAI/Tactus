Feature: Session Filters
  As a workflow developer
  I want to use session filters to control conversation history
  So that I can manage context and token usage effectively

  Background:
    Given a Tactus validation environment

  Scenario: last_n filter
    Given a Lua DSL file with content:
      """
      agent("worker", {
        provider = "openai",
        system_prompt = "Work",
        tools = {},
        session = {
          source = "own",
          filter = filters.last_n(10)
        }
      })

      main = procedure("main", function()
        return { result = "done" }
      end)
      """
    When I validate the file
    Then validation should succeed

  Scenario: token_budget filter
    Given a Lua DSL file with content:
      """
      agent("worker", {
        provider = "openai",
        system_prompt = "Work",
        tools = {},
        session = {
          source = "own",
          filter = filters.token_budget(4000)
        }
      })

      main = procedure("main", function()
        return { result = "done" }
      end)
      """
    When I validate the file
    Then validation should succeed

  Scenario: by_role filter
    Given a Lua DSL file with content:
      """
      agent("worker", {
        provider = "openai",
        system_prompt = "Work",
        tools = {},
        session = {
          source = "own",
          filter = filters.by_role("user")
        }
      })

      main = procedure("main", function()
        return { result = "done" }
      end)
      """
    When I validate the file
    Then validation should succeed

  Scenario: compose multiple filters
    Given a Lua DSL file with content:
      """
      agent("worker", {
        provider = "openai",
        system_prompt = "Work",
        tools = {},
        session = {
          source = "own",
          filter = filters.compose(
            filters.by_role("user"),
            filters.last_n(5)
          )
        }
      })

      main = procedure("main", function()
        return { result = "done" }
      end)
      """
    When I validate the file
    Then validation should succeed

  Scenario: Agent without filters
    Given a Lua DSL file with content:
      """
      agent("worker", {
        provider = "openai",
        system_prompt = "Work",
        tools = {}
      })

      main = procedure("main", function()
        return { result = "done" }
      end)
      """
    When I validate the file
    Then validation should succeed
