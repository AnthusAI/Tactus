-- Test Raw module with minimal formatting
WorldRaw = Agent {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = "Your name is World.",
    module = "Raw"  -- Use raw module for minimal overhead
}

Specification([[
Feature: Raw module

  Scenario: Returns raw output
    Given the procedure has started
    And the message is "Hello, World!"
    And the agent "WorldRaw" responds with "Hello! I'm World, nice to meet you!"
    When the procedure runs
    Then the output should be "Hello! I'm World, nice to meet you!"
]])

return WorldRaw("Hello, World!")
