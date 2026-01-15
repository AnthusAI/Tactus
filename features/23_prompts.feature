Feature: Prompt Templates
  As a workflow developer
  I want to define reusable prompt templates
  So that I can maintain consistent prompts across agents

  Background:
  Given a Tactus validation environment

  Scenario: Simple prompt template
  Given a Lua DSL file with content:
  """
  Prompt "greeting" "Hello, {input.name}! How can I help you today?"

  worker = Agent {
  provider = "openai",
  system_prompt = prompts.greeting,
  tools = {}
  }

  main = Procedure "main" {
  input = {
  name = field.string{default = "User"}
  },
  function(input)
  return { result = "done" }
  end
  }
  """
  When I validate the file
  Then validation should succeed

  Scenario: Multiple prompt templates
  Given a Lua DSL file with content:
  """
  Prompt "intro" "Welcome to the system"
  Prompt "task" "Please complete the following task"
  Prompt "outro" "Thank you for using our service"

  worker = Agent {
  provider = "openai",
  system_prompt = prompts.intro,
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

  Scenario: Multi-line prompt template
  Given a Lua DSL file with content:
  """
  Prompt "detailed" [[
  You are a helpful assistant.
  Your goal is to help the user.
  Be concise and accurate.
  ]]

  worker = Agent {
  provider = "openai",
  system_prompt = prompts.detailed,
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

  Scenario: Prompt template with input substitution
  Given a Lua DSL file with content:
  """
  Prompt "task_prompt" "Research the topic: {input.topic}"

  researcher = Agent {
  provider = "openai",
  system_prompt = prompts.task_prompt,
  tools = {}
  }

  main = Procedure "main" {
  input = {
  name = field.string{required = true}
  },
  function(input)
  return { result = "done" }
  end
  }
  """
  When I validate the file
  Then validation should succeed
