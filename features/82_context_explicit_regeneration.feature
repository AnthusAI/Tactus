Feature: Explicit Context Regeneration
  As a Tactus developer
  I want explicit Context packs to regenerate under budget pressure
  So that explicit plans still shrink pack outputs

  Scenario: Explicit Context re-queries retrievers under tight budget
    Given an explicit Context with retriever packs and tight budget
    When I assemble that explicit Context with regeneration
    Then the explicit retrievers should be called with progressively smaller budgets
