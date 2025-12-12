Feature: Output Schema Declarations
  As a workflow developer
  I want to declare typed output schemas
  So that I can validate return values and ensure consistent APIs

  Background:
    Given a Tactus validation environment

  Scenario: Simple string output
    Given a Lua DSL file with content:
      """
      output("result", {
        type = "string",
        required = true,
        description = "The result"
      })
      
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
    And it should recognize 1 output declaration

  Scenario: Multiple output fields with different types
    Given a Lua DSL file with content:
      """
      output("summary", {
        type = "string",
        required = true
      })
      
      output("count", {
        type = "number",
        required = true
      })
      
      output("success", {
        type = "boolean",
        required = false
      })
      
      agent("worker", {
        provider = "openai",
        system_prompt = "Work",
        tools = {}
      })
      
      procedure(function()
        return {
          summary = "All done",
          count = 42,
          success = true
        }
      end)
      """
    When I validate the file
    Then validation should succeed
    And it should recognize 3 output declarations

  Scenario: Optional output field
    Given a Lua DSL file with content:
      """
      output("result", {
        type = "string",
        required = true
      })
      
      output("details", {
        type = "string",
        required = false,
        description = "Optional details"
      })
      
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
    And it should recognize 2 output declarations

  @spec_mismatch @output_validation_not_enforced
  Scenario: Output schema validation at runtime
    # TODO: SPEC.md says outputs should be validated after execution (lines 152-158)
    # "When outputs: is present: 1. Required fields are validated to exist
    #  2. Types are checked 3. Only declared fields are returned"
    # Current implementation stores output schema but doesn't validate at runtime
    # Fix in: tactus/core/runtime.py - add output validation after procedure returns
    Given a Lua DSL file with content:
      """
      output("result", {
        type = "string",
        required = true
      })
      
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

  Scenario: Array output type
    Given a Lua DSL file with content:
      """
      output("items", {
        type = "array",
        required = true,
        description = "List of items"
      })
      
      agent("worker", {
        provider = "openai",
        system_prompt = "Work",
        tools = {}
      })
      
      procedure(function()
        return { items = {"a", "b", "c"} }
      end)
      """
    When I validate the file
    Then validation should succeed
    And it should recognize 1 output declaration

  Scenario: Object output type
    Given a Lua DSL file with content:
      """
      output("metadata", {
        type = "object",
        required = false,
        description = "Metadata object"
      })
      
      agent("worker", {
        provider = "openai",
        system_prompt = "Work",
        tools = {}
      })
      
      procedure(function()
        return { metadata = {key = "value"} }
      end)
      """
    When I validate the file
    Then validation should succeed
    And it should recognize 1 output declaration


