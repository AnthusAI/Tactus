-- Test Raw module streaming
Story = Agent {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = "You are a storyteller.",
    module = "Raw"  -- Use raw module for minimal overhead
}

Specification([[
Feature: Raw module streaming

  Scenario: Returns a short story
    Given the procedure has started
    And the message is "Tell me a very short story about a robot."
    And the agent "Story" responds with "Once a robot learned to whisper stories in oil and starlight."
    When the procedure runs
    Then the output should be "Once a robot learned to whisper stories in oil and starlight."
]])

return Story("Tell me a very short story about a robot.")
