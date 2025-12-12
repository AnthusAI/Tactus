Feature: Parameter Declarations
  As a workflow developer
  I want to declare typed parameters with validation
  So that I can ensure correct inputs and generate UIs automatically

  Background:
    Given a Tactus validation environment

  Scenario: Simple string parameter with default value
    Given a Lua DSL file with content:
      """
      parameter("name", {
        type = "string",
        default = "World"
      })
      
      agent("worker", {
        provider = "openai",
        system_prompt = "Hello {params.name}",
        tools = {}
      })
      
      procedure(function()
        return { greeting = "Hello, " .. params.name }
      end)
      """
    When I validate the file
    Then validation should succeed
    And it should recognize 1 parameter declaration

  Scenario: Required parameter validation
    Given a Lua DSL file with content:
      """
      parameter("topic", {
        type = "string",
        required = true,
        description = "Research topic"
      })
      
      agent("worker", {
        provider = "openai",
        system_prompt = "Research {params.topic}",
        tools = {}
      })
      
      procedure(function()
        return { result = params.topic }
      end)
      """
    When I validate the file
    Then validation should succeed
    And it should recognize 1 parameter declaration

  Scenario: Multiple parameter types
    Given a Lua DSL file with content:
      """
      parameter("name", {
        type = "string",
        required = true
      })
      
      parameter("count", {
        type = "number",
        default = 5
      })
      
      parameter("enabled", {
        type = "boolean",
        default = true
      })
      
      agent("worker", {
        provider = "openai",
        system_prompt = "Process {params.name}",
        tools = {}
      })
      
      procedure(function()
        return { 
          name = params.name,
          count = params.count,
          enabled = params.enabled
        }
      end)
      """
    When I validate the file
    Then validation should succeed
    And it should recognize 3 parameter declarations

  @spec_mismatch @enum_not_validated_at_runtime
  Scenario: Parameter with enum values
    # TODO: SPEC.md shows enum validation at runtime (lines 112-114)
    # Current implementation only validates enum at parse time
    # The registry stores enum but runtime doesn't validate against it
    # Fix in: tactus/core/runtime.py - add parameter validation before execution
    Given a Lua DSL file with content:
      """
      parameter("level", {
        type = "string",
        enum = {"low", "medium", "high"},
        default = "medium"
      })
      
      agent("worker", {
        provider = "openai",
        system_prompt = "Level: {params.level}",
        tools = {}
      })
      
      procedure(function()
        return { level = params.level }
      end)
      """
    When I validate the file
    Then validation should succeed
    And it should recognize 1 parameter declaration

  Scenario: Parameter used in template substitution
    Given a Lua DSL file with content:
      """
      parameter("topic", {
        type = "string",
        default = "AI"
      })
      
      agent("worker", {
        provider = "openai",
        system_prompt = "You are researching: {params.topic}",
        tools = {}
      })
      
      procedure(function()
        return { result = "done" }
      end)
      """
    When I validate the file
    Then validation should succeed
    And the agent system_prompt should contain "{params.topic}"

  Scenario: Parameter accessed in Lua code
    Given a Lua DSL file with content:
      """
      parameter("multiplier", {
        type = "number",
        default = 2
      })
      
      agent("worker", {
        provider = "openai",
        system_prompt = "Calculate",
        tools = {}
      })
      
      procedure(function()
        local result = 10 * params.multiplier
        return { result = result }
      end)
      """
    When I validate the file
    Then validation should succeed


