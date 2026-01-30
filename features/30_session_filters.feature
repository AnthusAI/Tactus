Feature: Session Filters
  As a workflow developer
  I want to use session filters to control conversation history
  So that I can manage context and token usage effectively

  Background:
  Given a Tactus validation environment

  Scenario: last_n filter
  Given a Lua DSL file with content:
  """
  worker = Agent {
  provider = "openai",
  system_prompt = "Work",
  tools = {},
  message_history = {
  source = "own",
  filter = filters.last_n(10)
  }
  }

  main = Procedure "main" {
    function(input)
  return { result = "done" }
  end
  }
  """
  When I validate the file
  Then validation should succeed

  Scenario: token_budget filter
  Given a Lua DSL file with content:
  """
  worker = Agent {
  provider = "openai",
  system_prompt = "Work",
  tools = {},
  message_history = {
  source = "own",
  filter = filters.token_budget(4000)
  }
  }

  main = Procedure "main" {
    function(input)
  return { result = "done" }
  end
  }
  """
  When I validate the file
  Then validation should succeed

  Scenario: by_role filter
  Given a Lua DSL file with content:
  """
  worker = Agent {
  provider = "openai",
  system_prompt = "Work",
  tools = {},
  message_history = {
  source = "own",
  filter = filters.by_role("user")
  }
  }

  main = Procedure "main" {
    function(input)
  return { result = "done" }
  end
  }
  """
  When I validate the file
  Then validation should succeed

  Scenario: first_n filter
  Given a Lua DSL file with content:
  """
  worker = Agent {
  provider = "openai",
  system_prompt = "Work",
  tools = {},
  message_history = {
  source = "own",
  filter = filters.first_n(3)
  }
  }

  main = Procedure "main" {
    function(input)
  return { result = "done" }
  end
  }
  """
  When I validate the file
  Then validation should succeed

  Scenario: head_tokens filter
  Given a Lua DSL file with content:
  """
  worker = Agent {
  provider = "openai",
  system_prompt = "Work",
  tools = {},
  message_history = {
  source = "own",
  filter = filters.head_tokens(2048)
  }
  }

  main = Procedure "main" {
    function(input)
  return { result = "done" }
  end
  }
  """
  When I validate the file
  Then validation should succeed

  Scenario: tail_tokens filter
  Given a Lua DSL file with content:
  """
  worker = Agent {
  provider = "openai",
  system_prompt = "Work",
  tools = {},
  message_history = {
  source = "own",
  filter = filters.tail_tokens(2048)
  }
  }

  main = Procedure "main" {
    function(input)
  return { result = "done" }
  end
  }
  """
  When I validate the file
  Then validation should succeed

  Scenario: system_prefix filter
  Given a Lua DSL file with content:
  """
  worker = Agent {
  provider = "openai",
  system_prompt = "Work",
  tools = {},
  message_history = {
  source = "own",
  filter = filters.system_prefix()
  }
  }

  main = Procedure "main" {
    function(input)
  return { result = "done" }
  end
  }
  """
  When I validate the file
  Then validation should succeed

  Scenario: compose multiple filters
  Given a Lua DSL file with content:
  """
  worker = Agent {
  provider = "openai",
  system_prompt = "Work",
  tools = {},
  message_history = {
  source = "own",
  filter = filters.compose(
  filters.by_role("user"),
  filters.last_n(5)
  )
  }
  }

  main = Procedure "main" {
    function(input)
  return { result = "done" }
  end
  }
  """
  When I validate the file
  Then validation should succeed

  Scenario: Agent without filters
  Given a Lua DSL file with content:
  """
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
