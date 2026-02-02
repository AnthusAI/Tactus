Feature: Default Context Pack Priority
  As a Tactus developer
  I want default Context pack budgets to respect priority
  So that higher-priority packs receive more of the shared budget

  Scenario: Default Context allocates shared budget by priority
    Given a default Context with prioritized packs and a shared budget
    When I assemble that default Context with shared pack budgets
    Then higher-priority packs should receive greater or equal budgets
    And total pack budget should not exceed the shared limit
