Feature: Session Filters
  As a workflow developer
  I want to use session filters to control conversation history
  So that I can manage context and token usage effectively

  Background:
    Given a Tactus validation environment

  @spec_mismatch @filters_not_used_at_runtime
  Scenario: last_n filter
    # TODO: SPEC.md describes session filters (lines 828-834)
    # Current implementation defines filter functions but doesn't apply them at runtime
    # Filters should be used in agent session configuration
    # Fix in: tactus/core/runtime.py - apply filters to agent sessions
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
      
      procedure(function()
        return { result = "done" }
      end)
      """
    When I validate the file
    Then validation should succeed

  @spec_mismatch @filters_not_used_at_runtime
  Scenario: token_budget filter
    # TODO: Same as above - filters defined but not applied
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
      
      procedure(function()
        return { result = "done" }
      end)
      """
    When I validate the file
    Then validation should succeed

  @spec_mismatch @filters_not_used_at_runtime
  Scenario: by_role filter
    # TODO: Same as above - filters defined but not applied
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
      
      procedure(function()
        return { result = "done" }
      end)
      """
    When I validate the file
    Then validation should succeed

  @spec_mismatch @filters_not_used_at_runtime
  Scenario: compose multiple filters
    # TODO: Same as above - filters defined but not applied
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
      
      procedure(function()
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
      
      procedure(function()
        return { result = "done" }
      end)
      """
    When I validate the file
    Then validation should succeed
