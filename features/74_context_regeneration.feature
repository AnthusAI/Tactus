Feature: Context Regeneration Loop
  As a Tactus developer
  I want context packs to regenerate when budgets tighten
  So that contexts converge within limits

  Scenario: Regeneration loop tightens retriever budget
    Given a Context with a small input budget and retriever pack
    When I assemble that Context with regeneration
    Then the retriever should be called with progressively smaller budgets
