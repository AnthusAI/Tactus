Feature: Explicit Context Pack Weights
  As a Tactus developer
  I want explicit Context packs to respect weights under shared budgets
  So that explicit plans still honor weights when regenerating

  Scenario: Explicit Context allocates shared budget by weight
    Given an explicit Context with weighted packs and tight budget
    When I assemble that explicit Context with regeneration for weights
    Then higher-weighted explicit packs should receive greater or equal budgets
