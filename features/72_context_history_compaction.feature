Feature: Context History Compaction
  As a Tactus developer
  I want history to be compacted when budgets are exceeded
  So that prompts stay within limits

  Scenario: History messages are trimmed when over budget
    Given a Context with a tight history budget
    When I assemble that Context with history compaction
    Then the history should be shortened
