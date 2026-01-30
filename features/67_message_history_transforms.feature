Feature: Message History Transforms
  As a workflow developer
  I want to transform conversation histories
  So that I can reset, rewind, and slice histories deterministically

  Background:
    Given a Tactus runtime environment

  Scenario: MessageHistory provides reset, head/tail, rewind, and token slicing
    Given an example file "11-feature-message-history-transforms.tac"
    When I execute the procedure
    Then the execution should succeed
    And the output should contain field "system_reset_count" with value 2
    And the output should contain field "head_count" with value 3
    And the output should contain field "tail_count" with value 2
    And the output should contain field "tail_tokens_count" with value 2
    And the output should contain field "rewind_count" with value 5
    And the output should contain field "rewind_to_count" with value 5
    And the output should contain field "keep_tail_count" with value 3
    And the output should contain field "keep_head_count" with value 4
    And the output should contain field "has_message_ids" with value true
