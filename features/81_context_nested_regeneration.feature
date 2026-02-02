Feature: Nested Context Regeneration
  As a Tactus developer
  I want nested Context packs to regenerate under tight budgets
  So that nested retrievers shrink their output when needed

  Scenario: Nested Context re-queries under tight outer budget
    Given a nested Context pack with a retriever and tight outer budget
    When I assemble the outer Context with regeneration
    Then the nested retriever should be called with progressively smaller budgets
