Feature: Result Object from Agent Turns
  As a workflow developer
  I want agents to return Result objects with data, usage, and messages
  So that I can track token usage and access conversation history
  
  Scenario: Agent turn returns a Result object
    Given a simple workflow file with an agent
    And a Lua procedure that calls an agent
    When the procedure executes
    Then the agent should return a result object
    And the result should have a data property
  
  Scenario: Result object has usage information
    Given a simple workflow file with an agent
    And a Lua procedure that calls an agent
    When the procedure executes
    Then the result should have usage information
    And usage should include total_tokens
    And usage should include prompt_tokens
    And usage should include completion_tokens
  
  Scenario: Result object provides message access
    Given a simple workflow file with an agent
    And a Lua procedure that calls an agent
    When the procedure executes
    Then the result should have new_messages method
    And the result should have all_messages method
  
  Scenario: Result data is accessible in Lua
    Given a simple workflow file with an agent
    And a procedure that logs the result data
    When the procedure executes
    Then the procedure should complete successfully
    And the output should contain result information




