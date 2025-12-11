Feature: Lua Integration
  As a workflow developer
  I want to write workflow logic in Lua
  So that I can use a familiar scripting language with sandboxing

  Background:
    Given a Tactus workflow environment
    And a Lua sandbox is initialized

  Scenario: Executing simple Lua code
    When I execute Lua code:
      """
      local result = 2 + 2
      return result
      """
    Then the result should be 4

  Scenario: Accessing primitives from Lua
    Given primitives are available in Lua environment
    When I execute Lua code:
      """
      state:set("counter", 0)
      state:increment("counter")
      return state:get("counter")
      """
    Then the result should be 1
    And state "counter" should equal 1

  Scenario: Lua functions and control flow
    When I execute Lua code:
      """
      function fibonacci(n)
        if n <= 1 then return n end
        return fibonacci(n-1) + fibonacci(n-2)
      end
      return fibonacci(10)
      """
    Then the result should be 55

  Scenario: Lua tables and data structures
    When I execute Lua code:
      """
      local data = {
        name = "Alice",
        scores = {95, 87, 92}
      }
      return data
      """
    Then the result should be a Python dict
    And it should have field "name" with value "Alice"
    And field "scores" should be a list with 3 elements

  Scenario: Sandboxing prevents dangerous operations
    When I execute Lua code that tries to access "os.execute"
    Then the code should be blocked
    And an error should be raised about restricted access

  Scenario: Calling Python functions from Lua
    Given a Python function "multiply" is exported to Lua
    When I execute Lua code:
      """
      return multiply(6, 7)
      """
    Then the result should be 42

  Scenario: Iterating with Lua loops
    When I execute Lua code:
      """
      local sum = 0
      for i = 1, 10 do
        sum = sum + i
      end
      return sum
      """
    Then the result should be 55

  Scenario: Error handling in Lua
    When I execute Lua code:
      """
      local success, result = pcall(function()
        error("Intentional error")
      end)
      return success
      """
    Then the result should be false
    And no Python exception should be raised

  Scenario: Multi-line Lua workflow
    When I execute Lua code:
      """
      -- Initialize workflow state
      state:set("status", "starting")

      -- Call agent
      local response = agent:call("What is 2+2?")

      -- Save result
      state:set("agent_response", response)
      state:set("status", "completed")

      return state:get("status")
      """
    Then the result should be "completed"
    And state "agent_response" should contain agent output
