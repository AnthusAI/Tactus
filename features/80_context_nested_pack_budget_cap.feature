Feature: Nested Context Pack Budget Cap
  As a Tactus developer
  I want outer pack budgets to cap nested pack retrieval
  So that nested packs respect the outer budget constraints

  Scenario: Outer pack budget caps nested retriever output
    Given a nested Context pack with a retriever and an outer pack budget
    When I assemble the outer Context with a budgeted nested pack
    Then the nested retriever should receive the capped budget
