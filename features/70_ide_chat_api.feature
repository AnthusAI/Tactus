Feature: IDE Chat API
  As an IDE client
  I want chat endpoints to respond predictably
  So that conversations can be managed

  Background:
    Given a chat API client

  Scenario: Start a conversation
    When I start a chat conversation
    Then the chat start response should be active

  Scenario: Chat test endpoint
    When I ping the chat test endpoint
    Then the chat test response should be ok

  Scenario: Send and retrieve messages
    When I start a chat conversation
    And I send a chat message "Hello"
    Then the chat response should include events
    When I request the chat history
    Then the chat history should include the message

  Scenario: Resume and clear a conversation
    When I resume a chat conversation
    Then the chat resume response should be active
    When I clear the chat conversation
    Then the chat should be removed

  Scenario: Stream a chat response
    When I stream a chat message "Hi"
    Then the stream response should be event-stream

  Scenario: Start conversation requires workspace
    When I start a chat conversation without a workspace
    Then the chat error should mention "workspace_root required"

  Scenario: Message requires conversation id
    When I send a chat message without a conversation id
    Then the chat error should mention "conversation_id and message required"

  Scenario: History requires known conversation
    When I request history for an unknown conversation
    Then the chat error should mention "Conversation not found"

  Scenario: Clear requires known conversation
    When I clear an unknown conversation
    Then the chat error should mention "Conversation not found"

  Scenario: Stream requires workspace
    When I stream a chat message without a workspace
    Then the chat error should mention "workspace_root and message required"
