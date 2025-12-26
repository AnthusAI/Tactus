Feature: Script Mode Entry Points
  As a workflow developer
  I want to write procedures in script mode without explicit procedure definitions
  So that I can write simpler, more concise workflow files

  Background:
    Given a Tactus validation environment

  Scenario: Top-level input declaration is recognized
    Given a Lua DSL file with content:
      """
      input {
        name = {type = "string", required = true}
      }

      main = procedure("main", {
        output = {result = {type = "string", required = true}},
        state = {}
      }, function()
        return {result = "Hello, " .. input.name}
      end)
      """
    When I validate the file
    Then validation should succeed

  Scenario: Top-level output declaration is recognized
    Given a Lua DSL file with content:
      """
      output {
        greeting = {type = "string", required = true}
      }

      main = procedure("main", {
        input = {name = {type = "string", default = "World"}},
        state = {}
      }, function()
        return {greeting = "Hello, " .. input.name}
      end)
      """
    When I validate the file
    Then validation should succeed

  Scenario: Script mode with top-level input and output
    Given a Lua DSL file with content:
      """
      input {
        value = {type = "number", default = 42}
      }

      output {
        result = {type = "number", required = true}
      }

      main = procedure("main", {state = {}}, function()
        return {result = input.value * 2}
      end)
      """
    When I validate the file
    Then validation should succeed

  Scenario: Multiple input fields in script mode
    Given a Lua DSL file with content:
      """
      input {
        first_name = {type = "string", required = true},
        last_name = {type = "string", required = true},
        age = {type = "number", default = 0}
      }

      output {
        full_name = {type = "string", required = true}
      }

      main = procedure("main", {state = {}}, function()
        return {full_name = input.first_name .. " " .. input.last_name}
      end)
      """
    When I validate the file
    Then validation should succeed

  Scenario: Multiple output fields in script mode
    Given a Lua DSL file with content:
      """
      input {
        text = {type = "string", default = "test"}
      }

      output {
        length = {type = "number", required = true},
        uppercase = {type = "string", required = true},
        lowercase = {type = "string", required = true}
      }

      main = procedure("main", {state = {}}, function()
        return {
          length = #input.text,
          uppercase = string.upper(input.text),
          lowercase = string.lower(input.text)
        }
      end)
      """
    When I validate the file
    Then validation should succeed
