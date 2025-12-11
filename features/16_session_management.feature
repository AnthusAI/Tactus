Feature: Session Management
  As a workflow developer
  I want to manage chat sessions with agents
  So that I can maintain conversation context and history

  Background:
    Given a Tactus workflow environment
    And the session primitive is initialized
    And a chat recorder is configured

  Scenario: Starting a new session
    When I start a new session with context:
      | key           | value                    |
      | task_type     | research                 |
      | user_id       | user_123                 |
    Then a session should be created
    And it should have a unique session_id
    And the context should be stored

  Scenario: Recording messages in a session
    Given an active session
    When I record a user message "What is machine learning?"
    And I record an assistant message "Machine learning is..."
    Then both messages should be stored in the session
    And they should be in chronological order

  Scenario: Retrieving session history
    Given a session with 5 messages
    When I retrieve the session history
    Then I should get all 5 messages
    And they should include role, content, and timestamps

  Scenario: Session with human interactions
    Given an active session
    When an agent requests human approval
    And I record the approval request
    And I record the human response
    Then the session should show the HITL interaction
    And it should be marked as a human_interaction message

  Scenario: Ending a session
    Given an active session with messages
    When I end the session with status "completed"
    Then the session should be marked as completed
    And the final status should be recorded
    And no more messages can be added

  Scenario: Session with metadata
    Given a session with custom metadata:
      | key               | value        |
      | workflow_name     | research     |
      | iteration         | 3            |
      | model_version     | gpt-4        |
    When I retrieve the session
    Then all metadata should be included
    And it can be used for filtering and analysis

  Scenario: Multiple concurrent sessions
    Given I start session "session_a" for workflow "workflow_1"
    And I start session "session_b" for workflow "workflow_2"
    When I add messages to both sessions
    Then each session should maintain independent message history
    And messages should not cross between sessions

  Scenario: Session recovery after failure
    Given a session that was interrupted
    When I retrieve the session by ID
    Then I should get all messages recorded before interruption
    And I can resume the conversation

  Scenario: Exporting session transcript
    Given a completed session with multiple messages
    When I export the session as JSON
    Then it should include all messages, metadata, and timestamps
    And it should be a valid transcript format

  Scenario: Session analytics
    Given multiple completed sessions
    When I query sessions by task_type "research"
    Then I should get all research sessions
    And I can calculate metrics like:
      | metric                    |
      | average_session_duration  |
      | message_count             |
      | human_interactions        |
