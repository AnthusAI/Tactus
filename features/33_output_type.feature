Feature: Structured Output with output_type
  As a workflow developer
  I want to define output_type schemas for agents
  So that I get validated, type-safe structured data from LLMs
  
  Scenario: Define output_type in agent configuration
    Given a workflow with an agent that has output_type defined
    When the workflow is validated
    Then the workflow validates successfully
  
  Scenario: output_type schema is recognized in DSL
    Given the example file "structured-output-demo.tac"
    When the file is validated
    Then it should parse successfully
    And it should have an agent with output_type
  
  Scenario: output_type converts to Pydantic model
    Given the example file "structured-output-demo.tac"
    When the workflow is validated
    Then the workflow validates successfully
  
  Scenario: output_type supports multiple field types
    Given a simple workflow file with agents
    And a workflow with output_type including:
      | type     |
      | string   |
      | number   |
      | boolean  |
    When the workflow is parsed
    Then all field types should be recognized
    And the types should map correctly




