Feature: Tool Integration
  As a workflow developer
  I want to call external tools via MCP
  So that workflows can interact with external systems

  Background:
    Given a Tactus workflow with MCP server configured
    And the tool primitive is initialized

  Scenario: Calling a simple tool
    When I call tool "get_weather" with parameters:
      | parameter | value      |
      | location  | San Francisco |
    Then the tool should execute successfully
    And the result should contain weather data

  Scenario: Tool call with error handling
    When I call tool "invalid_tool" with parameters:
      | parameter | value |
      | foo       | bar   |
    Then the tool call should fail
    And an error should be raised

  Scenario: Chaining tool calls
    Given tool "search_papers" returns paper IDs
    When I call "search_papers" with query "machine learning"
    And I call "get_paper_details" for each result
    Then I should have detailed information for all papers

  Scenario: Tool call with timeout
    When I call tool "long_running_task" with timeout 5 seconds
    And the tool takes longer than 5 seconds
    Then the call should timeout
    And a timeout error should be raised

  Scenario: Parallel tool execution
    When I call multiple tools in parallel:
      | tool          | parameters           |
      | get_weather   | location=NYC         |
      | get_news      | category=technology  |
      | get_stocks    | symbol=AAPL          |
    Then all tools should execute concurrently
    And results should be collected when all complete
