Feature: Example Procedures
  As a Tactus user
  I want all example procedures to execute successfully
  So that I can trust the examples as reference implementations

  Background:
    Given a Tactus runtime environment

  Scenario Outline: Example procedure executes successfully
    Given an example file "<example_file>"
    When I execute the procedure
    Then the execution should succeed
    And the output should match the declared schema

    Examples: Lua DSL Examples
      | example_file                    |
      | hello-world.tac              |
      | state-management.tac         |
      | with-parameters.tac          |
      | simple-agent.tac             |
      | multi-model.tac              |

  Scenario: Hello World example produces correct output
    Given an example file "hello-world.tac"
    When I execute the procedure
    Then the execution should succeed
    And the output should contain field "success" with value true
    And the output should contain field "count" with value 5

  Scenario: State Management example tracks count correctly
    Given an example file "state-management.tac"
    When I execute the procedure
    Then the execution should succeed
    And the output should contain field "success" with value true
    And the output should contain field "count" with value 5

  Scenario: With Parameters example uses defaults
    Given an example file "with-parameters.tac"
    When I execute the procedure
    Then the execution should succeed
    And the output should contain field "result" with value "Completed default task with 3 iterations"







