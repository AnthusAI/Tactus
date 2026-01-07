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
    name = field.string{required = true}
  }

  main = Procedure "main" {
    output = {
      result = field.string{required = true}
    },
    function(input)
      return {result = "Hello, " .. input.name}
    end
  }
  """
  When I validate the file
  Then validation should succeed

  Scenario: Top-level output declaration is recognized
  Given a Lua DSL file with content:
  """
  output {
    greeting = field.string{required = true}
  }

  main = Procedure "main" {
  input = {
  name = field.string{default = "World"}
  },
  function(input)
  return {greeting = "Hello, " .. input.name}
  end
  }
  """
  When I validate the file
  Then validation should succeed

  Scenario: Script mode with top-level input and output
  Given a Lua DSL file with content:
  """
  input {
    value = field.number{default = 42}
  }

  output {
    result = field.number{required = true}
  }

  main = Procedure "main" {state = {},
  function(input)
  return {result = input.value * 2}
  end
  }
  """
  When I validate the file
  Then validation should succeed

  Scenario: Multiple input fields in script mode
  Given a Lua DSL file with content:
  """
  input {
    first_name = field.string{required = true},
    last_name = field.string{required = true},
  age = field.number{default = 0}
  }

  output {
    full_name = field.string{required = true}
  }

  main = Procedure "main" {state = {},
  function(input)
  return {full_name = input.first_name .. " " .. input.last_name}
  end
  }
  """
  When I validate the file
  Then validation should succeed

  Scenario: Multiple output fields in script mode
  Given a Lua DSL file with content:
  """
  input {
    text = field.string{default = "test"}
  }

  output {
    length = field.number{required = true},
  uppercase = field.string{required = true},
  lowercase = field.string{required = true}
  }

  main = Procedure "main" {state = {},
  function(input)
  return {
  length = #input.text,
  uppercase = string.upper(input.text),
  lowercase = string.lower(input.text)
  }
  end
  }
  """
  When I validate the file
  Then validation should succeed
