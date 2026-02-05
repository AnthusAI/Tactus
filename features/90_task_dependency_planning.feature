Feature: Task dependency planning
  As a workflow developer
  I want load/extract/index dependencies to be planned and enforced
  So that retrievers are ready before run executes

  Scenario: Auto-deps builds extraction and index snapshots
    Given a NOAA corpus fixture copy
    And a task workflow that uses the copied corpus
    When I run "tactus run --no-sandbox --auto-deps" on the file
    Then the command should succeed
    And an extraction snapshot should exist
    And a retrieval snapshot should exist

  Scenario: Prompt accepts dependency execution
    Given a NOAA corpus fixture copy
    And a task workflow that uses the copied corpus
    And I provide CLI input "y"
    When I run "tactus run --no-sandbox" on the file
    Then the command should succeed
    And an extraction snapshot should exist

  Scenario: No-deps fails fast when dependencies are missing
    Given a NOAA corpus fixture copy
    And a task workflow that uses the copied corpus
    When I run "tactus run --no-sandbox --no-deps" on the file
    Then the command should fail
    And the output should show "Dependencies missing"

  Scenario: Index task fans out across multiple retrievers
    Given a NOAA corpus fixture copy
    And a task workflow with two retrievers
    When I run "tactus run --no-sandbox --auto-deps index" on the file
    Then the command should succeed
    And at least 2 retrieval snapshots should exist

  Scenario: Load handler runs for empty corpus
    Given an empty corpus workspace
    And a task workflow with a load provider
    When I run "tactus run --no-sandbox --auto-deps" on the file
    Then the command should succeed
    And the load marker should exist
