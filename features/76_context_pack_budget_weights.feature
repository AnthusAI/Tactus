Feature: Context Pack Budget Weights
  As a Tactus developer
  I want to weight pack budgets
  So that some packs get more space

  Scenario: Weighted pack budgets allocate more tokens
    Given a Context with weighted retriever packs
    When I assemble that Context with weighted budgets
    Then the higher-weighted pack should receive a larger budget
