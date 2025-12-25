-- Multi-Model Workflow Example
-- Demonstrates using multiple OpenAI models in one procedure

-- Agents (defined at top level - reusable across procedures)
agent("researcher", {
    provider = "openai",
    model = "gpt-4o",
    system_prompt = [[You are a researcher. Provide brief research findings (2-3 paragraphs maximum).
IMPORTANT: You MUST call the 'done' tool when finished, passing your research as the 'reason' argument.
]],
    initial_message = "Please research this topic and call done when finished: {input.topic}",
})

agent("summarizer", {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = [[You are a summarizer. Create a brief 1-2 paragraph summary of the provided text.
IMPORTANT: You MUST call the 'done' tool when finished, passing your summary as the 'reason' argument.
]],
    initial_message = "Please summarize the following research and call done when finished:\n\n{research}",
})

-- Procedure with input defined inline
procedure({
    input = {
        topic = {
            type = "string",
            default = "artificial intelligence",
        },
    },
    state = {
        research = {
            type = "string",
            default = "",
            description = "Research findings"
        }
    }
}, function()
    -- Research phase with GPT-4o
    Log.info("Starting research with GPT-4o...")
    local max_turns = 3
    local turn_count = 0
    local result

    repeat
      result = Researcher.turn()
      turn_count = turn_count + 1
    until Tool.called("done") or turn_count >= max_turns

    local research
    if Tool.called("done") then
        research = Tool.last_call("done").args.reason
    else
        research = result.text or "Research not completed"
        Log.warn("Researcher did not call done within max turns")
    end
    State.set("research", research)

    -- Summarization phase with GPT-4o-mini
    Log.info("Creating summary with GPT-4o-mini...")
    turn_count = 0

    repeat
      result = Summarizer.turn()
      turn_count = turn_count + 1
    until Tool.called("done") or turn_count >= max_turns

    local summary
    if Tool.called("done") then
        summary = Tool.last_call("done").args.reason
    else
        summary = result.text or "Summary not completed"
        Log.warn("Summarizer did not call done within max turns")
    end

    return {
      research = research,
      summary = summary,
      models_used = {"gpt-4o", "gpt-4o-mini"}
    }
end)

-- BDD Specifications
specifications([[
Feature: Multi-Model Workflow
  Demonstrate using multiple OpenAI models in one procedure

  Scenario: Research and summarization workflow
    Given the procedure has started
    When the procedure runs
    Then the done tool should be called exactly 2 times
    And the procedure should complete successfully
    And the state research should exist
]])
