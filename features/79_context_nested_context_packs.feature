Feature: Nested Context Pack Composition
  As a Tactus developer
  I want nested Context packs to include other context packs
  So that pack composition remains recursive and expressive

  Scenario: Nested Context pack composes retriever pack content
    Given a nested Context pack that includes another context pack
    When I assemble the outer Context
    Then the nested pack should include the composed context content
