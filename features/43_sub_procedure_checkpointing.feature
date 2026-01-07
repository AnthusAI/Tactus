Feature: Sub-Procedure Auto-Checkpointing
  As a workflow developer
  I want sub-procedure calls to be automatically checkpointed
  So that nested workflows are durable and can be replayed

  Background:
  Given a Tactus validation environment

  Scenario: Sub-procedure calls are recognized in validation
  Given a Lua DSL file with content:
  """
  main = Procedure "main" {
    input = {
      value = field.number{}
    },
    state = {},
    function(input)
      local sub_result = Procedure.run("helper", {x = input.value})
  return {result = sub_result}
  end
  }
  """
  When I validate the file
  Then validation should succeed

  Scenario: Nested procedures can be composed
  Given a Lua DSL file with content:
  """
  helper = Procedure "helper" {
    input = {x = field.number{},},
    function(input)
      return input.x * 2
    end
  }

  main = Procedure "main" {
    function(input)
      local result = helper({x = 10})
      return {result = result}
    end
  }
  """
  When I validate the file
  Then validation should succeed

  Scenario: Multiple sub-procedures can be called
  Given a Lua DSL file with content:
  """
  add = Procedure "add" {
    input = {a = field.number{}, b = field.number{},},
    function(input)
      return input.a + input.b
    end
  }

  multiply = Procedure "multiply" {
    input = {a = field.number{}, b = field.number{},},
    function(input)
      return input.a * input.b
    end
  }

  main = Procedure "main" {
    function(input)
      local sum = add({a = 5, b = 3})
      local product = multiply({a = sum, b = 2})
      return {result = product}
    end
  }
  """
  When I validate the file
  Then validation should succeed

  Scenario: Recursive procedure calls are supported
  Given a Lua DSL file with content:
  """
  factorial = Procedure "factorial" {
    input = {n = field.number{},},
    function(input)
      if input.n <= 1 then
        return 1
      else
        local prev = factorial({n = input.n - 1})
        return input.n * prev
      end
    end
  }

  main = Procedure "main" {
    function(input)
      local result = factorial({n = 5})
      return {result = result}
    end
  }
  """
  When I validate the file
  Then validation should succeed

  Scenario: Sub-procedure execution is checkpointed
  Given a Lua DSL file with content:
  """
  expensive = Procedure "expensive" {
    function(input)
      -- Simulate expensive operation
      return "computed_value"
    end
  }

  main = Procedure "main" {
    state = {cached = field.string{},},
    function(input)
      -- Sub-procedure call should be automatically checkpointed
      state.cached = expensive({})
      return {result = state.cached}
    end
  }
  """
  When I validate the file
  Then validation should succeed
  And the state_schema should contain field "cached"
