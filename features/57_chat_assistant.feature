Feature: Chat Assistant with File Tools
  As a developer using the Tactus IDE
  I want to chat with an AI assistant that can read files
  So that I can get help understanding my codebase

  Background:
    Given a workspace at "examples/"
    And the chat assistant is configured with:
      | parameter   | value    |
      | provider    | openai   |
      | model       | gpt-4o   |
      | temperature | 0.7      |

  Scenario: Basic chat without tools
    When I send the message "Hello"
    Then the assistant should respond
    And the response should contain text
    And no tools should be called

  Scenario: View a file
    When I send the message "Show me 01-basics-hello-world.tac"
    Then the assistant should call tool "str_replace_based_edit_tool"
    And the tool should be called with:
      | parameter | value                          |
      | command   | view                           |
      | path      | 01-basics-hello-world.tac      |
    And the tool result should contain line numbers
    And the response should describe the file contents

  Scenario: List directory contents
    When I send the message "What files are in this directory?"
    Then the assistant should call tool "str_replace_based_edit_tool"
    And the tool should be called with:
      | parameter | value |
      | command   | view  |
      | path      | .     |
    And the tool result should show directories and files
    And the response should list the files

  Scenario: View specific line range
    Given a workspace at "."
    And the chat assistant is configured with:
      | parameter   | value    |
      | provider    | openai   |
      | model       | gpt-4o   |
      | temperature | 0.7      |
    When I send the message "Show me lines 10-20 of tactus/validation/validator.py"
    Then the assistant should call tool "str_replace_based_edit_tool"
    And the tool should be called with:
      | parameter  | value                            |
      | command    | view                             |
      | path       | tactus/validation/validator.py   |
      | view_range | [10, 20]                         |
    And the tool result should contain exactly 11 lines

  Scenario: Security - reject path outside workspace
    When I send the message "Show me /etc/passwd"
    Then the assistant should call tool "str_replace_based_edit_tool"
    And the tool result should contain "Error"
    And the tool result should contain "outside workspace"
