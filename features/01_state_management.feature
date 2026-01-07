Feature: State Management
  As a workflow developer
  I want to maintain mutable state across workflow steps
  So that I can track progress and accumulate results

  Background:
  Given a fresh Tactus workflow environment
  And the state primitive is initialized

  Scenario: Getting and setting simple values
  When I set state "user_name" to "Alice"
  Then state "user_name" should equal "Alice"

  Scenario: Using default values for missing keys
  When I get state "missing_key" with default "default_value"
  Then the result should equal "default_value"
  And state "missing_key" should not exist

  Scenario: Incrementing numeric counters
  Given state "iteration_count" is 0
  When I increment state "iteration_count"
  Then state "iteration_count" should equal 1
  When I increment state "iteration_count" by 5
  Then state "iteration_count" should equal 6

  Scenario: Building lists by appending values
  When I append "first_item" to state "items"
  And I append "second_item" to state "items"
  And I append "third_item" to state "items"
  Then state "items" should be a list with 3 elements
  And state "items" should contain "first_item", "second_item", and "third_item"

  Scenario: Tracking workflow progress
  Given I am building an AI research workflow
  When I set state "phase" to "exploration"
  And I set state "hypotheses_filed" to 0
  And I increment state "hypotheses_filed"
  And I increment state "hypotheses_filed"
  And I append "hypothesis_1" to state "hypothesis_list"
  And I append "hypothesis_2" to state "hypothesis_list"
  Then state "phase" should equal "exploration"
  And state "hypotheses_filed" should equal 2
  And state "hypothesis_list" should have 2 items
