Feature: Human-in-the-Loop Interactions
  As a workflow developer
  I want to request human input during workflow execution
  So that humans can approve, review, and guide AI decisions

  Background:
    Given a Tactus workflow with HITL enabled
    And a CLI HITL handler is configured

  Scenario: Requesting human approval
    When the workflow requests approval with message "Deploy to production?"
    And the human approves the request
    Then the workflow should continue
    And the approval result should be true

  Scenario: Human rejection stops the workflow path
    When the workflow requests approval with message "Delete all data?"
    And the human rejects the request
    Then the approval result should be false
    And the workflow can handle the rejection

  Scenario: Requesting human input
    When the workflow requests input with prompt "Enter the topic:"
    And the human provides input "Climate change"
    Then the workflow should receive "Climate change"
    And the workflow can use the input

  Scenario: Review with multiple options
    Given the workflow has generated a research report
    When the workflow requests review with message "Review this report"
    And options are "approve", "request_changes", "reject"
    And the human selects "request_changes" with feedback "Add more citations"
    Then the workflow should receive decision "request_changes"
    And the workflow should receive feedback "Add more citations"

  Scenario: Timeout returns default value
    When the workflow requests approval with message "Proceed?" and timeout 1 second
    And the human does not respond
    And 2 seconds pass
    Then the workflow should receive the default value false
    And the workflow continues with the default

  Scenario: Escalation blocks until resolved
    Given the workflow encounters an unrecoverable error
    When the workflow escalates with message "Manual intervention required"
    And severity is "error"
    Then the workflow should pause
    And wait for human resolution
    When the human resolves the escalation
    Then the workflow should resume
