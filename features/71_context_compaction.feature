Feature: Context Compaction and Budgeting
  As a Tactus developer
  I want Context to compact itself when budgets are exceeded
  So that prompt assembly stays within limits

  Background:
    Given the Wikitext2 raw dataset is available

  Scenario: Context compactor truncates excess context
    Given a Context with a strict token budget and a retriever pack
    When I assemble that Context with compaction
    Then the assembled context should fit within the budget

  Scenario: Retriever re-queries when budget is lowered
    Given a Context with a tight pack budget and a retriever pack
    When I assemble that Context with compaction
    Then the retriever should be re-queried with a smaller budget

  Scenario: Retriever tightens budget after initial compaction
    Given a Context with a strict token budget and a retriever pack
    When I assemble that Context with compaction
    Then the retriever should be re-queried with a tighter budget
