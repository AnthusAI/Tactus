Feature: Control Flow
  As a workflow developer
  I want to use conditional logic and loops
  So that I can create dynamic, adaptive workflows

  Background:
    Given a Tactus workflow environment
    And the control primitive is initialized

  Scenario: Simple if-then condition
    Given state "temperature" is 75
    When I evaluate condition "temperature > 70"
    Then the condition should be true
    And the then-branch should execute

  Scenario: If-then-else with false condition
    Given state "score" is 45
    When I evaluate condition "score >= 50"
    Then the condition should be false
    And the else-branch should execute

  Scenario: Nested conditions
    Given state "level" is 3
    And state "points" is 150
    When I evaluate "level > 2 AND points >= 100"
    Then the condition should be true
    And nested logic should execute correctly

  Scenario: Loop through a list
    Given state "items" contains ["apple", "banana", "cherry"]
    When I iterate over "items"
    Then each item should be processed
    And iteration count should be 3

  Scenario: Early exit from loop
    Given state "numbers" contains [1, 2, 3, 4, 5]
    When I iterate over "numbers" with break condition "number == 3"
    Then iteration should stop at 3
    And remaining items should not be processed
