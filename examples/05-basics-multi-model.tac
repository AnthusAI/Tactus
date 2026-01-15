-- Multi-Model Workflow Example
-- Demonstrates using multiple OpenAI models in one procedure

local done = require("tactus.tools.done")

-- Agents (defined at top level - reusable across procedures)
researcher = Agent {
    provider = "openai",
    model = "gpt-4o",
    system_prompt = [[You are a researcher. Provide brief research findings (2-3 paragraphs maximum).
IMPORTANT: You MUST call the 'done' tool when finished, passing your research as the 'reason' argument.
]],
    initial_message = "Please research this topic and call done when finished: {input.topic}",
    tools = {done},
}

summarizer = Agent {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = [[You are a summarizer. Create a brief 1-2 paragraph summary of the provided text.
IMPORTANT: You MUST call the 'done' tool when finished, passing your summary as the 'reason' argument.
]],
    initial_message = "Please summarize the following research and call done when finished:\n\n{research}",
    tools = {done},
}

-- Procedure with input defined inline
Procedure {
    input = {
        topic = field.string{default = "artificial intelligence"},
    },
    function(input)
        -- Research phase with GPT-4o
        Log.info("Starting research with GPT-4o...")
        local max_turns = 3
        local turn_count = 0
        local result

        repeat
          result = researcher()
          turn_count = turn_count + 1
        until done.called() or turn_count >= max_turns

        local research
        if done.called() then
            research = done.last_result() or "Task completed"
        else
            if result and result.output ~= nil then
                research = tostring(result.output)
            else
                research = "Research not completed"
            end
            Log.warn("Researcher did not call done within max turns")
        end
        state.research = research

        -- Reset done tool for next agent
        done.reset()

        -- Summarization phase with GPT-4o-mini
        Log.info("Creating summary with GPT-4o-mini...")
        turn_count = 0

        repeat
          result = summarizer()
          turn_count = turn_count + 1
        until done.called() or turn_count >= max_turns

        local summary
        if done.called() then
            summary = done.last_result() or "Task completed"
        else
            if result and result.output ~= nil then
                summary = tostring(result.output)
            else
                summary = "Summary not completed"
            end
            Log.warn("Summarizer did not call done within max turns")
        end

        return {
          research = research,
          summary = summary,
          models_used = {"gpt-4o", "gpt-4o-mini"}
        }
    end
}

-- BDD Specifications
Specification([[
Feature: Multi-Model Workflow
  Demonstrate using multiple OpenAI models in one procedure

  Scenario: Research and summarization workflow
    Given the procedure has started
    And the agent "researcher" responds with "I have researched the topic and found key insights about artificial intelligence."
    And the agent "researcher" calls tool "done" with args {"reason": "Research findings on artificial intelligence"}
    And the agent "summarizer" responds with "Here is a concise summary of the research findings."
    And the agent "summarizer" calls tool "done" with args {"reason": "Summary of AI research"}
    When the procedure runs
    Then the done tool should be called at least 1 time
    And the procedure should complete successfully
]])
