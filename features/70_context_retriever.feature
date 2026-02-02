Feature: Context Retriever with Wikitext2
  As a Tactus developer
  I want to retrieve real context from a small corpus
  So that I can test context packs in CI

  Background:
    Given the Wikitext2 raw dataset is available

  Scenario: Retrieve context pack from Wikitext2
    Given a Context with a Wikitext2 retriever for query "Valkyria Chronicles III"
    When I assemble that Context
    Then the assembled context should include "Valkyria Chronicles III"
