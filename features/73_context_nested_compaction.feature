Feature: Nested Context Compaction
  As a Tactus developer
  I want nested context packs to honor pack budgets
  So that composed contexts remain predictable

  Scenario: Nested context pack is compacted by pack budget
    Given a Context with a nested pack and a tight pack budget
    When I assemble that Context with nested compaction
    Then the nested context should be compacted