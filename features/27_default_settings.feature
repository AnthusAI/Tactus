Feature: Default Provider and Model Settings
  As a workflow developer
  I want to set default provider and model for all agents
  So that I don't have to repeat them in every agent definition

  Background:
  Given a Tactus validation environment

  Scenario: Default provider setting
  Given a Lua DSL file with content:
  """
  default_provider = "openai"

  worker = Agent {
  system_prompt = "Work",
  tools = {}
  }

  main = Procedure "main" {
    function(input)
      return { result = "done" }
    end
  }
  """
  When I validate the file
  Then validation should succeed

  Scenario: Default model setting
  Given a Lua DSL file with content:
  """
  default_model = "gpt-4o-mini"

  worker = Agent {
  provider = "openai",
  system_prompt = "Work",
  tools = {}
  }

  main = Procedure "main" {
    function(input)
      return { result = "done" }
    end
  }
  """
  When I validate the file
  Then validation should succeed

  Scenario: Both default provider and model
  Given a Lua DSL file with content:
  """
  default_provider = "openai"
  default_model = "gpt-4o"

  worker = Agent {
  system_prompt = "Work",
  tools = {}
  }

  main = Procedure "main" {
    function(input)
      return { result = "done" }
    end
  }
  """
  When I validate the file
  Then validation should succeed

  Scenario: Agent overrides default provider
  Given a Lua DSL file with content:
  """
  default_provider = "openai"

  worker = Agent {
  provider = "bedrock",
  system_prompt = "Work",
  tools = {}
  }

  main = Procedure "main" {
    function(input)
      return { result = "done" }
    end
  }
  """
  When I validate the file
  Then validation should succeed

  Scenario: Multiple agents with defaults
  Given a Lua DSL file with content:
  """
  default_provider = "openai"
  default_model = "gpt-4o-mini"

  worker1 = Agent {
  system_prompt = "Work 1",
  tools = {}
  }

  worker2 = Agent {
  system_prompt = "Work 2",
  tools = {}
  }

  main = Procedure "main" {
    function(input)
      return { result = "done" }
    end
  }
  """
  When I validate the file
  Then validation should succeed
