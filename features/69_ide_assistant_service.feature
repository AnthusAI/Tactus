Feature: IDE Assistant Service
  As an IDE user
  I want assistant conversations to be managed safely
  So that responses and history are tracked

  Background:
    Given an assistant service with a workspace

  Scenario: Start and resume a conversation
    When I start a conversation "conv-1"
    Then the conversation should be active
    When I resume the conversation "conv-1"
    Then the conversation should be marked as resumed

  Scenario: Send message without starting
    When I send a message without starting a conversation
    Then I should receive an error event

  Scenario: Send message with streaming response
    When I start a conversation "conv-2"
    And I send a message "Hello assistant"
    Then I should receive assistant output
    And the assistant history should include the exchange
    When I clear the conversation "conv-2"
    Then the conversation history should be empty
