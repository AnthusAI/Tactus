Feature: Default Context Pack Weights
  As a Tactus developer
  I want default Context pack budgets to respect weights
  So that weighted packs receive more of the shared budget

  Scenario: Default Context allocates shared budget by weight
    Given a default Context with weighted packs and a shared budget
    When I assemble that default Context with weighted shared pack budgets
    Then higher-weighted packs should receive greater or equal budgets in default Context
