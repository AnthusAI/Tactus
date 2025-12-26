Feature: Input Declarations (Procedure Parameters)
  As a workflow developer
  I want to declare typed inputs with validation
  So that I can ensure correct inputs and generate UIs automatically

  Background:
    Given a Tactus validation environment

  Scenario: Simple string input with default value
    Given a Lua DSL file with content:
      """
      agent("worker", {
        provider = "openai",
        system_prompt = "Hello {input.name}",
        tools = {}
      })

      main = procedure("main", {
        input = {
          name = {
            type = "string",
            default = "World"
          }
        }
      }, function()
        return { greeting = "Hello, " .. input.name }
      end)
      """
    When I validate the file
    Then validation should succeed
    And the input_schema should contain field "name"

  Scenario: Required input validation
    Given a Lua DSL file with content:
      """
      agent("worker", {
        provider = "openai",
        system_prompt = "Research {input.topic}",
        tools = {}
      })

      main = procedure("main", {
        input = {
          topic = {
            type = "string",
            required = true,
            description = "Research topic"
          }
        }
      }, function()
        return { result = input.topic }
      end)
      """
    When I validate the file
    Then validation should succeed
    And the input_schema should contain field "topic"

  Scenario: Multiple input types
    Given a Lua DSL file with content:
      """
      agent("worker", {
        provider = "openai",
        system_prompt = "Process {input.name}",
        tools = {}
      })

      main = procedure("main", {
        input = {
          name = {
            type = "string",
            required = true
          },
          count = {
            type = "number",
            default = 5
          },
          enabled = {
            type = "boolean",
            default = true
          }
        }
      }, function()
        return {
          name = input.name,
          count = input.count,
          enabled = input.enabled
        }
      end)
      """
    When I validate the file
    Then validation should succeed
    And the input_schema should have 3 fields

  Scenario: Input with enum values
    Given a Lua DSL file with content:
      """
      agent("worker", {
        provider = "openai",
        system_prompt = "Level: {input.level}",
        tools = {}
      })

      main = procedure("main", {
        input = {
          level = {
            type = "string",
            enum = {"low", "medium", "high"},
            default = "medium"
          }
        }
      }, function()
        return { level = input.level }
      end)
      """
    When I validate the file
    Then validation should succeed
    And the input_schema should contain field "level"

  Scenario: Input used in template substitution
    Given a Lua DSL file with content:
      """
      agent("worker", {
        provider = "openai",
        system_prompt = "You are researching: {input.topic}",
        tools = {}
      })

      main = procedure("main", {
        input = {
          topic = {
            type = "string",
            default = "AI"
          }
        }
      }, function()
        return { result = "done" }
      end)
      """
    When I validate the file
    Then validation should succeed
    And the agent system_prompt should contain "{input.topic}"

  Scenario: Input accessed in Lua code
    Given a Lua DSL file with content:
      """
      agent("worker", {
        provider = "openai",
        system_prompt = "Calculate",
        tools = {}
      })

      main = procedure("main", {
        input = {
          multiplier = {
            type = "number",
            default = 2
          }
        }
      }, function()
        local result = 10 * input.multiplier
        return { result = result }
      end)
      """
    When I validate the file
    Then validation should succeed
