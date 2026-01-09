Feature: Explicit Checkpoint Primitive
  As a workflow developer
  I want to manually checkpoint state at specific points
  So that I can control when state is persisted and enable selective replay

  Background:
  Given a Tactus validation environment

  Scenario: Checkpoint() function is available globally
  Given a Lua DSL file with content:
  """
  main = Procedure "main" {
    output = {
      result = field.number{required = true}
    },
    state = {},
    function(input)
      Checkpoint()
      local result = 42
      return {result = result}
    end
  }
  """
  When I validate the file
  Then validation should succeed

  Scenario: Explicit checkpoints save state
  Given a Lua DSL file with content:
  """
  main = Procedure "main" {
    input = {
      value = field.number{default = 10}
    },
    state = {
      computed = field.number{default = 0}
    },
    function(input)
      Checkpoint()
      state.computed = input.value * 2
      return {result = state.computed}
    end
  }
  """
  When I validate the file
  Then validation should succeed

  Scenario: Multiple explicit checkpoints
  Given a Lua DSL file with content:
  """
  main = Procedure "main" {
    input = {
      value = field.number{default = 5}
    },
    output = {
      step1 = field.number{required = true},
      step2 = field.number{required = true},
      step3 = field.number{required = true}
    },
    state = {},
    function(input)
      Checkpoint()
      local step1 = input.value * 2

      Checkpoint()
      local step2 = step1 + 10

      Checkpoint()
      local step3 = step2 + 5

      return {step1 = step1, step2 = step2, step3 = step3}
    end
  }
  """
  When I validate the file
  Then validation should succeed

  Scenario: Checkpointing expensive operations
  Given a Lua DSL file with content:
  """
  processor = Agent {
    provider = "openai",
    system_prompt = "Work",
    tools = {}
  }

  main = Procedure "main" {
    function(input)
      Checkpoint()
      local result1 = Agent("processor")({query = "process data"})

      -- Second expensive operation
      Checkpoint()
      local result2 = Agent("processor")({query = "analyze results"})

      return {result = result1 .. " " .. result2}
    end
  }
  """
  When I validate the file
  Then validation should succeed

  Scenario: Checkpoint with state updates
  Given a Lua DSL file with content:
  """
  main = Procedure "main" {
    input = {
      count = field.number{default = 0}
    },
    output = {
      result = field.number{required = true}
    },
    state = {
      count = field.number{default = 0},
      total = field.number{default = 0}
    },
    function(input)
      state.count = state.count + 1
      Checkpoint()
      state.total = input.count + 1

      return {result = state.total}
    end
  }
  """
  When I validate the file
  Then validation should succeed
  And the state_schema should contain field "count"
  And the state_schema should contain field "total"

  Scenario: Checkpoint vs Checkpoint primitive
  Given a Lua DSL file with content:
  """
  worker = Agent {
    provider = "openai",
    system_prompt = "Work",
    tools = {}
  }

  main = Procedure "main" {
    function(input)
      -- Using Checkpoint function
      Checkpoint()
      local result1 = Agent("worker")({task = "task1"})

      return {result = result1}
    end
  }

  alt = Procedure "alt" {
    function(input)
      -- Using Checkpoint primitive (different syntax)
      local result2 = Checkpoint({task = "task2"})
      return {result = result2}
    end
  }
  """
  When I validate the file
  Then validation should succeed
