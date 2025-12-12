Feature: Lua DSL Validation
  As a workflow developer
  I want to validate my Lua DSL configuration files
  So that I can catch syntax and semantic errors before runtime

  Background:
    Given a Tactus validation environment

  Scenario: Valid Lua DSL file passes validation
    Given a Lua DSL file "examples/simple-agent.tac"
    When I validate the file
    Then validation should succeed
    And it should recognize the procedure declaration
    And it should recognize agent declarations
    And it should recognize output declarations

  Scenario: Invalid Lua syntax is detected
    Given a Lua DSL file with content:
      """
      -- Missing closing brace
      agent("worker", {
        provider = "openai",
        model = "gpt-4o"
      """
    When I validate the file
    Then validation should fail
    And the error should mention "syntax error"
    And the error should include a line number

  Scenario: Missing required procedure declaration
    Given a Lua DSL file with content:
      """
      -- No procedure() call
      agent("worker", {
        provider = "openai",
        model = "gpt-4o",
        system_prompt = "Test",
        tools = {}
      })
      """
    When I validate the file
    Then validation should fail
    And the error should mention "procedure declaration is required"

  Scenario: Missing required agent fields
    Given a Lua DSL file with content:
      """
      agent("worker", {
        model = "gpt-4o",
        system_prompt = "Test",
        tools = {}
      })
      """
    When I validate the file
    Then validation should fail
    And the error should mention "provider"

  Scenario: Valid parameter declaration
    Given a Lua DSL file with content:
      """
      parameter("topic", {
        type = "string",
        required = true,
        description = "Research topic"
      })
      
      agent("worker", {
        provider = "openai",
        model = "gpt-4o",
        system_prompt = "Test",
        tools = {}
      })
      
      procedure(function()
        return {}
      end)
      """
    When I validate the file
    Then validation should succeed
    And it should recognize 1 parameter declaration

  Scenario: Valid output declaration
    Given a Lua DSL file with content:
      """
      output("result", {
        type = "string",
        required = true,
        description = "Result"
      })
      
      agent("worker", {
        provider = "openai",
        model = "gpt-4o",
        system_prompt = "Test",
        tools = {}
      })
      
      procedure(function()
        return {}
      end)
      """
    When I validate the file
    Then validation should succeed
    And it should recognize 1 output declaration

  Scenario: Quick validation mode
    Given a Lua DSL file "examples/simple-agent.tac"
    When I validate the file in quick mode
    Then validation should succeed
    And it should only check syntax

  Scenario: Full validation mode
    Given a Lua DSL file "examples/simple-agent.tac"
    When I validate the file in full mode
    Then validation should succeed
    And it should check syntax
    And it should check semantic rules
    And it should validate required fields

  Scenario: All example files validate successfully
    Given the example Lua DSL files:
      | file                            |
      | simple-agent.tac             |
      | hello-world.tac              |
      | state-management.tac         |
      | with-parameters.tac          |
      | multi-model.tac              |
    When I validate each file
    Then all validations should succeed

  Scenario: CLI validation command for Lua DSL
    Given a Lua DSL file "examples/simple-agent.tac"
    When I run "tactus validate examples/simple-agent.tac"
    Then the command should succeed
    And the output should show "lua format"
    And the output should display procedure information

  Scenario: CLI validation shows helpful error messages
    Given a Lua DSL file with syntax error
    When I run "tactus validate" on the file
    Then the command should fail
    And the output should show the error location
    And the output should suggest how to fix it







