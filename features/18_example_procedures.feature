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
      | example_file                         |
      | hello-world.tac                      |
      | 02-basics-simple-logic.tac          |
      | 03-basics-parameters.tac             |
      | simple-agent.tac                     |
      | 05-basics-multi-model.tac           |
      | 06-basics-streaming.tac             |
      | 07-basics-bedrock.tac               |
      | 08-basics-models.tac                |
      | 10-feature-state.tac                 |
      | 11-feature-message-history.tac      |
      | 13-feature-session.tac              |
      | 14-feature-per-turn-tools-simple.tac|
      | 14-feature-per-turn-tools.tac       |
      | 15-feature-local-tools.tac          |
      | 16-feature-toolsets-advanced.tac    |
      | 17-feature-toolsets-dsl.tac         |

  Scenario: Hello World example produces correct output
    Given an example file "hello-world.tac"
    When I execute the procedure
    Then the execution should succeed
    And the output should contain field "success" with value true
    And the output should contain field "count" with value 5

  Scenario: State Management example tracks count correctly
    Given an example file "10-feature-state.tac"
    When I execute the procedure
    Then the execution should succeed
    And the output should contain field "success" with value true
    And the output should contain field "count" with value 5

  Scenario: With Parameters example uses defaults
    Given an example file "03-basics-parameters.tac"
    When I execute the procedure
    Then the execution should succeed
    And the output should contain field "result" with value "Completed default task with 3 iterations"











