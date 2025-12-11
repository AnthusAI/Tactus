Feature: Stage and Step Tracking
  As a workflow developer
  I want to track workflow progress through stages and steps
  So that I can monitor execution and provide status updates

  Background:
    Given a Tactus workflow environment
    And stage and step primitives are initialized

  Scenario: Defining workflow stages
    Given a workflow with stages:
      | stage_id    | name              |
      | stage1      | Data Collection   |
      | stage2      | Analysis          |
      | stage3      | Report Generation |
    When I begin stage "stage1"
    Then the current stage should be "Data Collection"
    And stage status should be "in_progress"

  Scenario: Completing stages in sequence
    Given a workflow with 3 stages
    When I complete stage 1
    And I begin stage 2
    Then stage 1 status should be "completed"
    And stage 2 status should be "in_progress"
    And stage 3 status should be "pending"

  Scenario: Tracking steps within a stage
    Given I am in stage "Analysis"
    When I begin step "load_data"
    And I complete step "load_data"
    And I begin step "process_data"
    Then stage "Analysis" should show 2 steps
    And step "load_data" should be completed
    And step "process_data" should be in_progress

  Scenario: Stage progress percentage
    Given a stage with 10 steps
    When 7 steps are completed
    Then stage progress should be 70%

  Scenario: Nested stages
    Given a parent stage "Research"
    And child stages "Literature Review" and "Experiments"
    When I complete "Literature Review"
    Then parent stage progress should reflect child completion
    And parent should be 50% complete

  Scenario: Step timing and duration
    When I begin step "expensive_operation"
    And 5 seconds pass
    And I complete step "expensive_operation"
    Then step duration should be approximately 5 seconds
    And I can identify slow steps

  Scenario: Stage failure handling
    Given I am in stage "Processing"
    When a step fails with an error
    Then the stage should be marked as "failed"
    And the failure reason should be recorded
    And I can retry the stage or skip to next stage

  Scenario: Resuming workflow at specific stage
    Given a workflow that failed at stage "Analysis"
    When I resume the workflow
    Then it should restart from stage "Analysis"
    And completed stages should be skipped

  Scenario: Real-time progress updates
    Given a long-running workflow
    When stages and steps complete
    Then progress updates should be emitted
    And external systems can monitor status
