Feature: Default Context Regeneration
  As a Tactus developer
  I want default Context packs to regenerate under budget pressure
  So that implicit plans remain stable

  Scenario: Default Context re-queries retriever under tight budget
    Given a default Context with a retriever pack and tight budget
    When I assemble that default Context
    Then the retriever should be called with progressively smaller budgets for default Context
