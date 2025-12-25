Feature: Output Schema Declarations
  As a workflow developer
  I want to declare typed output schemas
  So that I can validate return values and ensure consistent APIs

  Background:
    Given a Tactus validation environment

  Scenario: Simple string output
    Given a Lua DSL file with content:
      """
      agent("worker", {
        provider = "openai",
        system_prompt = "Work",
        tools = {}
      })

      procedure({
        output = {
          result = {
            type = "string",
            required = true,
            description = "The result"
          }
        }
      }, function()
        return { result = "done" }
      end)
      """
    When I validate the file
    Then validation should succeed
    And the output_schema should contain field "result"

  Scenario: Multiple output fields with different types
    Given a Lua DSL file with content:
      """
      agent("worker", {
        provider = "openai",
        system_prompt = "Work",
        tools = {}
      })

      procedure({
        output = {
          summary = {
            type = "string",
            required = true
          },
          count = {
            type = "number",
            required = true
          },
          success = {
            type = "boolean",
            required = false
          }
        }
      }, function()
        return {
          summary = "All done",
          count = 42,
          success = true
        }
      end)
      """
    When I validate the file
    Then validation should succeed
    And the output_schema should have 3 fields

  Scenario: Optional output field
    Given a Lua DSL file with content:
      """
      agent("worker", {
        provider = "openai",
        system_prompt = "Work",
        tools = {}
      })

      procedure({
        output = {
          result = {
            type = "string",
            required = true
          },
          details = {
            type = "string",
            required = false,
            description = "Optional details"
          }
        }
      }, function()
        return { result = "done" }
      end)
      """
    When I validate the file
    Then validation should succeed
    And the output_schema should have 2 fields

  Scenario: Output schema validation at runtime
    Given a Lua DSL file with content:
      """
      agent("worker", {
        provider = "openai",
        system_prompt = "Work",
        tools = {}
      })

      procedure({
        output = {
          result = {
            type = "string",
            required = true
          }
        }
      }, function()
        return { result = "done" }
      end)
      """
    When I validate the file
    Then validation should succeed

  Scenario: Array output type
    Given a Lua DSL file with content:
      """
      agent("worker", {
        provider = "openai",
        system_prompt = "Work",
        tools = {}
      })

      procedure({
        output = {
          items = {
            type = "array",
            required = true,
            description = "List of items"
          }
        }
      }, function()
        return { items = {"a", "b", "c"} }
      end)
      """
    When I validate the file
    Then validation should succeed
    And the output_schema should contain field "items"

  Scenario: Object output type
    Given a Lua DSL file with content:
      """
      agent("worker", {
        provider = "openai",
        system_prompt = "Work",
        tools = {}
      })

      procedure({
        output = {
          metadata = {
            type = "object",
            required = false,
            description = "Metadata object"
          }
        }
      }, function()
        return { metadata = {key = "value"} }
      end)
      """
    When I validate the file
    Then validation should succeed
    And the output_schema should contain field "metadata"
