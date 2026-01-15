World = Agent {
  provider = "openai",
  model = "gpt-4o-mini",
  system_prompt = "Your name is World."
}

Specification([[
Feature: Fuzzy Matching

  Scenario: High-threshold fuzzy match (nearly exact)
    Given the procedure has started
    And the message is "Hello, World!"
    And the agent "World" responds with "Hello! I'm World, nice to meet you!"
    When the procedure runs
    Then the output should fuzzy match "Hello! I'm World, nice to meet you!" with threshold 0.95

  Scenario: Medium-threshold fuzzy match (allows variation)
    Given the procedure has started
    And the message is "Hello, World!"
    And the agent "World" responds with "Hello! How can I assist you today?"
    When the procedure runs
    Then the output should fuzzy match "Hello! I'm World, nice to meet you!" with threshold 0.45

  Scenario: Default fuzzy match threshold
    Given the procedure has started
    And the message is "Hello, World!"
    And the agent "World" responds with "Hello! I'm World, nice to meet you!"
    When the procedure runs
    Then the output should fuzzy match "Hello! I'm World, nice to meet you!"
]])

return World("Hello, World!")
