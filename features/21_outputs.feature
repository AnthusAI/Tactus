Feature: Output Schema Declarations
  As a workflow developer
  I want to declare typed output schemas
  So that I can validate return values and ensure consistent APIs

  Background:
  Given a Tactus validation environment

  Scenario: Simple string output
  Given a Lua DSL file with content:
  """
  worker = Agent {
  provider = "openai",
  system_prompt = "Work",
  tools = {}
  }

  Procedure {
  output = {
    result = field.string{required = true, description = "The result"}
  },
  function(input)
  return { result = "done" }
  end
  }
  """
  When I validate the file
  Then validation should succeed
  And the output_schema should contain field "result"

  Scenario: Multiple output fields with different types
  Given a Lua DSL file with content:
  """
  worker = Agent {
  provider = "openai",
  system_prompt = "Work",
  tools = {}
  }

  Procedure {
  output = {
    result = field.string{required = true},
    count = field.number{required = true},
    success = field.boolean{required = false}
  },
  function(input)
  return {
  result = "All done",
  count = 42,
  success = true
  }
  end
  }
  """
  When I validate the file
  Then validation should succeed
  And the output_schema should have 3 fields

  Scenario: Optional output field
  Given a Lua DSL file with content:
  """
  worker = Agent {
  provider = "openai",
  system_prompt = "Work",
  tools = {}
  }

  Procedure {
  output = {
    result = field.string{required = true},
    details = field.string{required = false, description = "Optional details"}
  },
  function(input)
  return { result = "done" }
  end
  }
  """
  When I validate the file
  Then validation should succeed
  And the output_schema should have 2 fields

  Scenario: Output schema validation at runtime
  Given a Lua DSL file with content:
  """
  worker = Agent {
  provider = "openai",
  system_prompt = "Work",
  tools = {}
  }

  Procedure {
  output = {
    result = field.string{required = true}
  },
  function(input)
  return { result = "done" }
  end
  }
  """
  When I validate the file
  Then validation should succeed

  Scenario: Array output type
  Given a Lua DSL file with content:
  """
  worker = Agent {
  provider = "openai",
  system_prompt = "Work",
  tools = {}
  }

  Procedure {
  output = {
    items = field.array{required = true, description = "List of items"}
  },
  function(input)
  return { items = {"a", "b", "c"} }
  end
  }
  """
  When I validate the file
  Then validation should succeed
  And the output_schema should contain field "items"

  Scenario: Object output type
  Given a Lua DSL file with content:
  """
  worker = Agent {
  provider = "openai",
  system_prompt = "Work",
  tools = {}
  }

  Procedure {
  output = {
    metadata = field.object{required = false, description = "Metadata object"}
  },
  function(input)
  return { metadata = {key = "value"} }
  end
  }
  """
  When I validate the file
  Then validation should succeed
  And the output_schema should contain field "metadata"
