Feature: Context Pack Expansion
  As a Biblicus developer
  I want Context packs to paginate when they are under budget
  So that elastic contexts can expand when more evidence is available

  Scenario: Retriever expands pack with pagination
    Given a Context with an expandable retriever pack
    When I assemble that Context with expansion
    Then the retriever should be called with paginated offsets
    And the assembled context should include expanded content
