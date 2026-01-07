Feature: DSPy History Management
  As a Tactus developer
  I want to manage conversation history with DSPy
  So that I can build context-aware multi-turn applications

  Background:
    Given dspy is installed as a dependency

  # Basic History Operations

  Scenario: Create empty History
    When I create a History
    Then the history should be empty
    And the history should have 0 messages

  Scenario: Add message to History
    Given I create a History
    When I add a message to history
    Then the history should have 1 message
    And I can retrieve the messages

  Scenario: Add multiple messages
    Given I create a History
    When I add a user message "Hello"
    And I add an assistant message "Hi there!"
    And I add a user message "How are you?"
    Then the history should have 3 messages
    And the messages should be in order

  # Message Types

  Scenario: Add user message
    Given I create a History
    When I add a user message "What's the weather?"
    Then the history should contain a user message
    And the user message content should be "What's the weather?"

  Scenario: Add assistant message
    Given I create a History
    When I add an assistant message "The weather is sunny"
    Then the history should contain an assistant message
    And the assistant message content should be "The weather is sunny"

  Scenario: Add system message
    Given I create a History
    When I add a system message "You are a helpful assistant"
    Then the history should contain a system message
    And the system message content should be "You are a helpful assistant"

  # Tactus DSL Integration

  Scenario: History in Tactus procedure
    Given a Tactus procedure that uses History:
      """
      Procedure "test_history" {
        output = {
          message_count = field.number{required = true}
        },
        function(input)
          local history = History()

          -- Add some messages
          history:add({role = "user", content = "Hello"})
          history:add({role = "assistant", content = "Hi!"})

          -- Count messages (mock implementation)
          local count = 2

          return {message_count = count}
        end
      }
      """
    When the procedure is parsed and executed
    Then the procedure should complete successfully
    And the output message_count should be 2

  Scenario: History with conversation flow
    Given a Tactus procedure with conversation:
      """
      Procedure "test_conversation" {
        output = {
          has_context = field.boolean{required = true}
        },
        function(input)
          local history = History()

          -- Simulate a conversation
          history:add({role = "user", content = "What's 2+2?"})
          history:add({role = "assistant", content = "2+2 equals 4"})
          history:add({role = "user", content = "And 3+3?"})
          history:add({role = "assistant", content = "3+3 equals 6"})

          -- History maintains context
          return {has_context = true}
        end
      }
      """
    When the procedure is parsed and executed
    Then the procedure should complete successfully
    And the output has_context should be true

  # History Retrieval and Iteration

  Scenario: Retrieve all messages
    Given a History with multiple messages
    When I retrieve all messages
    Then I should get a list of messages
    And each message should have role and content

  Scenario: Iterate through history
    Given a History with messages:
      | role      | content           |
      | user      | First question    |
      | assistant | First answer      |
      | user      | Second question   |
      | assistant | Second answer     |
    When I iterate through the history
    Then I should process 4 messages in order

  Scenario: Get last message
    Given a History with multiple messages
    When I get the last message
    Then I should receive the most recent message
    And it should have the correct role and content

  Scenario: Get messages by role
    Given a History with mixed messages
    When I filter messages by role "user"
    Then I should only get user messages
    And no assistant or system messages

  # History Clearing and Modification

  Scenario: Clear history
    Given a History with 5 messages
    When I clear the history
    Then the history should be empty
    And the history should have 0 messages

  Scenario: Remove last message
    Given a History with 3 messages
    When I remove the last message
    Then the history should have 2 messages
    And the last message should be gone

  Scenario: Truncate history to length
    Given a History with 10 messages
    When I truncate history to 5 messages
    Then the history should have 5 messages
    And it should keep the most recent messages

  # DSPy Integration

  Scenario: Convert to DSPy History format
    Given a Tactus History with messages
    When I convert to DSPy format
    Then it should be compatible with DSPy modules
    And maintain all message information

  Scenario: Create from DSPy History
    Given a DSPy History object
    When I create a Tactus History from it
    Then all messages should be preserved
    And the format should be correct

  # History with Modules

  Scenario: Pass History to Module
    Given a Module with signature "question -> answer"
    And a History with previous Q&A pairs
    When I invoke the Module with the history
    Then the Module should use the history context
    And provide a contextually aware response

  Scenario: Module updates History
    Given a Module with signature "question -> answer"
    And an empty History
    When I invoke the Module and update history
    Then the history should contain the new Q&A pair
    And maintain proper message roles

  # Advanced History Features

  Scenario: History with metadata
    Given I create a History
    When I add a message with metadata:
      """
      {
        "role": "user",
        "content": "Hello",
        "timestamp": "2024-01-01T10:00:00Z",
        "user_id": "123"
      }
      """
    Then the message should include metadata
    And I can retrieve the metadata

  Scenario: History serialization
    Given a History with messages
    When I serialize the history to JSON
    Then I should get valid JSON
    And I can deserialize it back to History

  Scenario: History with token counting
    Given a History with messages
    When I count tokens in the history
    Then I should get the total token count
    And per-message token counts

  # Multi-turn Conversation Tracking

  Scenario: Track conversation turns
    Given a Tactus procedure with multi-turn tracking:
      """
      Procedure "test_turns" {
        output = {
          turn_count = field.number{required = true}
        },
        function(input)
          local history = History()
          local turns = 0

          -- Simulate multiple turns
          for i = 1, 3 do
            history:add({role = "user", content = "Question " .. i})
            history:add({role = "assistant", content = "Answer " .. i})
            turns = turns + 1
          end

          return {turn_count = turns}
        end
      }
      """
    When the procedure is parsed and executed
    Then the procedure should complete successfully
    And the output turn_count should be 3

  # History Persistence

  Scenario: Save History to storage
    Given a History with conversation
    When I save the history
    Then it should be persisted
    And I can load it later

  Scenario: Load History from storage
    Given a saved History
    When I load the history
    Then all messages should be restored
    And the order should be preserved

  # Error Handling

  Scenario: Error on invalid message format
    Given a History
    When I try to add an invalid message without role
    Then an error should be raised
    And the error should mention "role is required"

  Scenario: Error on invalid role type
    Given a History
    When I try to add a message with role "invalid"
    Then an error should be raised
    And the error should mention "invalid role"

  # History Context Management

  Scenario: History with context window
    Given a History with 100 messages
    When I set context window to 10
    Then only the last 10 messages should be used
    And older messages should be excluded

  Scenario: History with token limit
    Given a History approaching token limit
    When I add a new message exceeding the limit
    Then old messages should be truncated
    And the total tokens should stay within limit

  # Integration with Agents

  Scenario: Agent manages its own History
    Given a Tactus procedure with Agent and History:
      """
      Procedure "test_agent_history" {
        output = {
          has_history = field.boolean{required = true}
        },
        function(input)
          local history = History()

          -- Agent would use this history
          history:add({role = "system", content = "You are helpful"})
          history:add({role = "user", content = "Hello"})

          return {has_history = true}
        end
      }
      """
    When the procedure is parsed and executed
    Then the procedure should complete successfully
    And the output has_history should be true