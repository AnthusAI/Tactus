Feature: Sub-Procedure Auto-Checkpointing
  As a workflow developer
  I want sub-procedure calls to be automatically checkpointed
  So that nested workflows are durable and can be replayed

  Background:
    Given a Tactus validation environment

  Scenario: Sub-procedure calls are recognized in validation
    Given a Lua DSL file with content:
      """
      procedure({
        input = {value = {type = "number"}},
        output = {result = {type = "number"}},
        state = {}
      }, function()
        local sub_result = Procedure.run("helper", {x = input.value})
        return {result = sub_result}
      end)
      """
    When I validate the file
    Then validation should succeed

  Scenario: Nested procedures can be composed
    Given a Lua DSL file with content:
      """
      procedure({
        input = {
          numbers = {type = "array", default = {1, 2, 3}}
        },
        output = {
          sum = {type = "number", required = true}
        },
        state = {}
      }, function()
        local result = Procedure.run("examples/helpers/sum.tac", {
          values = input.numbers
        })
        return {sum = result.result or result}
      end)
      """
    When I validate the file
    Then validation should succeed

  Scenario: Multiple sub-procedures can be called
    Given a Lua DSL file with content:
      """
      procedure({
        input = {
          numbers = {type = "array", default = {2, 3}}
        },
        output = {
          sum = {type = "number", required = true},
          product = {type = "number", required = true}
        },
        state = {}
      }, function()
        local sum_result = Procedure.run("examples/helpers/sum.tac", {
          values = input.numbers
        })
        local product_result = Procedure.run("examples/helpers/product.tac", {
          values = input.numbers
        })
        return {
          sum = sum_result.result or sum_result,
          product = product_result.result or product_result
        }
      end)
      """
    When I validate the file
    Then validation should succeed

  Scenario: Recursive procedure calls are supported
    Given a Lua DSL file with content:
      """
      procedure({
        input = {n = {type = "number", default = 5}},
        output = {result = {type = "number", required = true}},
        state = {}
      }, function()
        if input.n <= 1 then
          return {result = 1}
        end
        local sub = Procedure.run("factorial.tac", {n = input.n - 1})
        return {result = input.n * (sub.result or sub)}
      end)
      """
    When I validate the file
    Then validation should succeed

  Scenario: Sub-procedure execution is checkpointed
    Given a Lua DSL file with content:
      """
      procedure({
        input = {values = {type = "array", default = {10, 20, 30}}},
        output = {total = {type = "number", required = true}},
        state = {checkpointed = {type = "boolean", default = false}}
      }, function()
        -- This sub-procedure call should be auto-checkpointed
        local result = Procedure.run("examples/helpers/sum.tac", {
          values = input.values
        })
        state.checkpointed = true
        return {total = result.result or result}
      end)
      """
    When I validate the file
    Then validation should succeed
    And the state_schema should contain field "checkpointed"
