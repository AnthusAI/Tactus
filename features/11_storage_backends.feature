Feature: Storage Backends
  As a workflow developer
  I want to use different storage backends
  So that I can persist state in memory, files, or databases

  Scenario: In-memory storage for testing
    Given a Tactus runtime with in-memory storage
    When I execute a workflow that sets state
    Then state should be stored in memory
    And it should be available within the same session
    But it should not persist after restart

  Scenario: File-based storage for persistence
    Given a Tactus runtime with file-based storage
    And storage directory is "~/.tactus/storage"
    When I execute a workflow that sets state "user" to "Alice"
    Then a file should be created in the storage directory
    And reading the file should show the state value
    When I restart the workflow
    Then state "user" should still equal "Alice"

  Scenario: Loading existing workflow state
    Given a workflow "research_task" was previously executed
    And checkpoints exist for steps 1, 2, 3
    And state contains accumulated results
    When I initialize the runtime with procedure_id "research_task"
    Then the storage backend should load existing metadata
    And checkpoints should be available
    And state should be restored

  Scenario: Checkpoint isolation between workflows
    Given two workflows "workflow_a" and "workflow_b"
    When "workflow_a" saves checkpoint "step1" with value "A"
    And "workflow_b" saves checkpoint "step1" with value "B"
    Then "workflow_a" checkpoint should contain "A"
    And "workflow_b" checkpoint should contain "B"
    And checkpoints should not interfere with each other

  Scenario: Clearing workflow state
    Given a workflow with multiple checkpoints
    And state contains multiple keys
    When I clear all checkpoints
    Then no checkpoints should exist
    But state should remain intact

  Scenario: Storage backend error handling
    Given a file-based storage with read-only directory
    When I try to save state
    Then a storage error should be raised
    And the error should be descriptive

  Scenario: Concurrent access to storage
    Given multiple workflow instances using the same storage
    When workflows run concurrently
    Then each workflow should have isolated state
    And no data corruption should occur

  Scenario: Storage migration
    Given a workflow using in-memory storage
    When I switch to file-based storage
    Then existing state should be preserved
    And the workflow should continue seamlessly
