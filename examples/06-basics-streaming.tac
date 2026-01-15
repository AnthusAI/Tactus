-- Streaming Example
-- Demonstrates real-time LLM response streaming in the IDE
-- Note: Streaming only works when NO structured outputs are defined

-- Simple agent that just writes text (no tools needed for streaming demo)
storyteller = Agent {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = [[You are a creative storyteller. Write engaging short stories.

When asked to write a story:
- Write ONE complete story (about 100-150 words)
- Make it vivid and engaging
- End naturally when the story is complete
- Do NOT ask follow-up questions
- Do NOT offer to continue or write more]],
}

Specification([[
Feature: Streaming

  Scenario: Returns a story for the prompt
    Given the procedure has started
    And the message is "Write a short story about a robot learning to paint."
    And the agent "storyteller" responds with "A curious robot dipped its brush into blue paint and discovered joy in every stroke."
    When the procedure runs
    Then the output story should be "A curious robot dipped its brush into blue paint and discovered joy in every stroke."
    And the output success should be true
]])

-- Procedure with input (but no output block to avoid breaking streaming)
Procedure {
    input = {
        prompt = field.string{description = "Story prompt", default = "Write a short story about a robot learning to paint."}
    },
    function(input)
        -- Call the agent to write the story using callable syntax
        local result = storyteller({message = input.prompt})

        return {
            story = result.output,
            success = true
        }
    end
}
