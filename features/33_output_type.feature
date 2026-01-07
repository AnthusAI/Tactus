Feature: Structured Output with output
  As a workflow developer
  I want to define output schemas for agents
  So that I get validated, type-safe structured data from LLMs

  Scenario: Define output in agent configuration
  Given a workflow with an agent that has output defined
  When the workflow is validated
  Then the workflow validates successfully

  Scenario: output schema is recognized in DSL
  Given the example file "structured-output-demo.tac"
  When the file is validated
  Then it should parse successfully
  And it should have an agent with output

  Scenario: output converts to Pydantic model
  Given the example file "structured-output-demo.tac"
  When the workflow is validated
  Then the workflow validates successfully

  Scenario: output supports multiple field types
  Given a simple workflow file with agents
  And a workflow with output including:
  | type  |
  | string  |
  | number  |
  | boolean  |
  When the workflow is parsed
  Then all field types should be recognized
  And the types should map correctly





