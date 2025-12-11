Feature: Procedure Calls
  As a workflow developer
  I want to call sub-workflows from main workflows
  So that I can build modular, reusable workflow components

  Background:
    Given a Tactus workflow environment
    And the procedure primitive is initialized

  Scenario: Calling a simple sub-procedure
    Given a sub-procedure "calculate_sum":
      """
      name: calculate_sum
      params:
        - a
        - b
      steps:
        - id: sum
          action: state.set
          params:
            key: result
            value: "{{ a + b }}"
      """
    When I call procedure "calculate_sum" with params:
      | param | value |
      | a     | 5     |
      | b     | 3     |
    Then the procedure should execute
    And it should return result 8

  Scenario: Sub-procedure with state isolation
    Given a main procedure with state "counter" = 10
    And a sub-procedure that sets state "counter" = 5
    When I call the sub-procedure
    Then the sub-procedure should see "counter" = 5
    But the main procedure should still see "counter" = 10
    And state should be isolated between procedures

  Scenario: Passing complex data to sub-procedures
    Given a sub-procedure "process_list"
    When I call it with a list parameter:
      | item    |
      | item1   |
      | item2   |
      | item3   |
    Then the sub-procedure should receive the full list
    And it can iterate and process each item

  Scenario: Nested procedure calls
    Given procedure "level1" calls procedure "level2"
    And procedure "level2" calls procedure "level3"
    When I execute procedure "level1"
    Then all three levels should execute
    And call stack should be tracked correctly
    And results should propagate back up

  Scenario: Error handling in sub-procedures
    Given a sub-procedure that raises an error
    When I call it from the main procedure
    Then the error should propagate to the caller
    And the main procedure can catch and handle it

  Scenario: Sub-procedure timeouts
    Given a sub-procedure with timeout 5 seconds
    When the sub-procedure runs longer than 5 seconds
    Then it should be terminated
    And a timeout error should be raised to caller

  Scenario: Reusing procedures with different parameters
    Given a generic "send_email" procedure
    When I call it multiple times with different recipients
    Then each call should be independent
    And emails should be sent to all recipients

  Scenario: Checkpointing in sub-procedures
    Given a main procedure that calls sub-procedures
    When a sub-procedure completes
    Then its result should be checkpointed
    And resuming the main procedure should skip the completed sub-procedure
