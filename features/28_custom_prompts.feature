Feature: Custom Prompts (return, error, status)
  As a workflow developer
  I want to customize return, error, and status prompts
  So that I can control how procedures communicate their results

  Background:
  Given a Tactus validation environment

  Scenario: Custom return_prompt
  Given a Lua DSL file with content:
  """
  return_prompt = "Summarize your work concisely"

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

  Scenario: Custom error_prompt
  Given a Lua DSL file with content:
  """
  error_prompt = "Explain what went wrong and any partial progress"

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

  Scenario: Custom status_prompt
  Given a Lua DSL file with content:
  """
  status_prompt = "Provide a brief progress update"

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

  Scenario: All three custom prompts
  Given a Lua DSL file with content:
  """
  return_prompt = "Summarize your work"
  error_prompt = "Explain the error"
  status_prompt = "Report progress"

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

  Scenario: Multi-line custom prompts
  Given a Lua DSL file with content:
  """
  return_prompt([[
  Summarize your work:
  - What was accomplished
  - Key findings
  ]])
  
  error_prompt([[
  Explain what went wrong:
  - What you were attempting
  - What failed
  ]])
  
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
