Feature: Workflow Checkpointing
  As a workflow developer
  I want expensive operations to be checkpointed
  So that workflows can resume without recomputing results

  Background:
    Given a Tactus workflow with checkpointing enabled
    And an in-memory storage backend

  Scenario: First execution runs the expensive operation
    Given I have never run checkpoint "expensive_calculation"
    When I execute step "expensive_calculation" that computes factorial(100)
    Then the operation should execute
    And the result should be checkpointed
    And the checkpoint "expensive_calculation" should exist

  Scenario: Replay returns cached result without recomputing
    Given checkpoint "expensive_calculation" contains result 42
    When I execute step "expensive_calculation" that computes factorial(100)
    Then the operation should NOT execute
    And the result should equal 42 from cache

  Scenario: Multiple checkpoints track workflow progress
    When I execute step "load_data" that loads training data
    And I execute step "train_model" that trains a model
    And I execute step "evaluate_model" that evaluates performance
    Then checkpoint "load_data" should exist
    And checkpoint "train_model" should exist
    And checkpoint "evaluate_model" should exist

  Scenario: Clearing checkpoints allows re-execution
    Given checkpoint "calculation" contains result 100
    When I clear all checkpoints
    And I execute step "calculation" that computes 2 + 2
    Then the operation should execute
    And the result should equal 4
    And the checkpoint "calculation" should contain 4
