Feature: Explicit Context Pack Priority
  As a Tactus developer
  I want explicit Context packs to respect priority under shared budgets
  So that explicit plans still honor priority when regenerating

  Scenario: Explicit Context allocates shared budget by priority
    Given an explicit Context with prioritized packs and tight budget
    When I assemble that explicit Context with regeneration for priority
    Then higher-priority explicit packs should receive greater or equal budgets
