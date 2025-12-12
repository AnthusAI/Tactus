Feature: Matchers (contains, equals, matches)
  As a workflow developer
  I want to use matchers for pattern matching
  So that I can validate strings and patterns in my workflows

  Background:
    Given a Tactus validation environment

  @spec_mismatch @matchers_not_documented_in_spec
  Scenario: contains matcher
    # TODO: Matchers (contains, equals, matches) are implemented in dsl_stubs.py
    # but are not documented in SPECIFICATION.md
    # Need to add documentation for these matchers
    # Document in: SPECIFICATION.md - add matchers section
    Given a Lua DSL file with content:
      """
      agent("worker", {
        provider = "openai",
        system_prompt = "Work",
        tools = {}
      })
      
      procedure(function()
        local text = "Hello World"
        local match = contains("World")
        -- Matchers return a tuple that can be used for validation
        return { result = "done" }
      end)
      """
    When I validate the file
    Then validation should succeed

  @spec_mismatch @matchers_not_documented_in_spec
  Scenario: equals matcher
    # TODO: Same as above - not documented in spec
    Given a Lua DSL file with content:
      """
      agent("worker", {
        provider = "openai",
        system_prompt = "Work",
        tools = {}
      })
      
      procedure(function()
        local text = "exact"
        local match = equals("exact")
        return { result = "done" }
      end)
      """
    When I validate the file
    Then validation should succeed

  @spec_mismatch @matchers_not_documented_in_spec
  Scenario: matches regex matcher
    # TODO: Same as above - not documented in spec
    Given a Lua DSL file with content:
      """
      agent("worker", {
        provider = "openai",
        system_prompt = "Work",
        tools = {}
      })
      
      procedure(function()
        local text = "test123"
        local match = matches("test[0-9]+")
        return { result = "done" }
      end)
      """
    When I validate the file
    Then validation should succeed

  Scenario: Multiple matchers in procedure
    Given a Lua DSL file with content:
      """
      agent("worker", {
        provider = "openai",
        system_prompt = "Work",
        tools = {}
      })
      
      procedure(function()
        local m1 = contains("test")
        local m2 = equals("exact")
        local m3 = matches("[a-z]+")
        return { result = "done" }
      end)
      """
    When I validate the file
    Then validation should succeed

  Scenario: Procedure without matchers
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
