Feature: Matchers (contains, equals, matches)
  As a workflow developer
  I want to use matchers for pattern matching
  So that I can validate strings and patterns in my workflows

  Background:
  Given a Tactus validation environment

  Scenario: contains matcher
  Given a Lua DSL file with content:
  """
  worker = Agent {
  provider = "openai",
  system_prompt = "Work",
  tools = {}
  }

  main = Procedure "main" {
    function(input)
  local text = "Hello World"
  local match = contains("World")
  -- Matchers return a tuple that can be used for validation
  return { result = "done" }
  end
  }
  """
  When I validate the file
  Then validation should succeed

  Scenario: equals matcher
  Given a Lua DSL file with content:
  """
  worker = Agent {
  provider = "openai",
  system_prompt = "Work",
  tools = {}
  }

  main = Procedure "main" {
    function(input)
  local text = "exact"
  local match = equals("exact")
  return { result = "done" }
  end
  }
  """
  When I validate the file
  Then validation should succeed

  Scenario: matches regex matcher
  Given a Lua DSL file with content:
  """
  worker = Agent {
  provider = "openai",
  system_prompt = "Work",
  tools = {}
  }

  main = Procedure "main" {
    function(input)
  local text = "test123"
  local match = matches("test[0-9]+")
  return { result = "done" }
  end
  }
  """
  When I validate the file
  Then validation should succeed

  Scenario: Multiple matchers in procedure
  Given a Lua DSL file with content:
  """
  worker = Agent {
  provider = "openai",
  system_prompt = "Work",
  tools = {}
  }

  main = Procedure "main" {
    function(input)
  local m1 = contains("test")
  local m2 = equals("exact")
  local m3 = matches("[a-z]+")
  return { result = "done" }
  end
  }
  """
  When I validate the file
  Then validation should succeed

  Scenario: Procedure without matchers
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
