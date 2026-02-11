-- Example: Trace Inspection Evaluators
-- This demonstrates evaluators that inspect execution traces:
-- tool calls, agent turns, and state changes

local done = require("tactus.tools.done")

-- Define a search tool for this example
search = Tool {
    description = "Search for information on a topic",
    input = {
        query = field.string{required = true, description = "Search query"}
    },
    function(args)
        return {results = "Search results for: " .. args.query}
    end
}

researcher = Agent {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = [[You are a research assistant.

When given a topic, search for information and then provide a summary.
1. First, call the 'search' tool with the topic
2. Then, call the 'done' tool with your findings]],
    initial_message = "Research: {topic}",
    tools = {search, done}
}

reviewer = Agent {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = [[You are a quality reviewer.

Review the research and call 'done' with your assessment.]],
    initial_message = "Review this research: {research}",
    tools = {done}
}

Procedure {
    input = {
            topic = field.string{required = true}
    },
    output = {
            research = field.string{required = true},
            reviewed = field.boolean{required = true}
    },
    function(input)

    -- Track state
        state.research_started = true

        -- Researcher does the work
        researcher()

        local research = "No research completed"
        if Tool.called("search") then
            state.search_completed = true

            -- Get research result
            if done.called() then
                research = done.last_result() or "Task completed" or "Research done"
                state.research_complete = true
            end
        end

        -- Reviewer checks the work
        reviewer()

        local reviewed = done.called()

        return {
            research = research,
            reviewed = reviewed
        }

    -- BDD Specifications
    end
}

Specification([[
Feature: Multi-Agent Research with Trace Inspection

  Scenario: Researcher searches and completes
    Given the procedure has started
    And the input topic is "Artificial Intelligence"
    And the agent "researcher" responds with "I've researched the topic and found relevant information."
    And the agent "researcher" calls tool "search" with args {"query": "Artificial Intelligence"}
    And the agent "researcher" calls tool "done" with args {"reason": "Research findings on AI topic."}
    And the agent "reviewer" responds with "I've reviewed the research."
    And the agent "reviewer" calls tool "done" with args {"reason": "The research looks good."}
    When the procedure runs
    Then the search tool should be called
    And the done tool should be called at least 1 time
    And the procedure should complete successfully
]])

-- Pydantic AI Evaluations with Trace Inspection
-- Note: Evaluations framework is partially implemented.
-- Commented out until field.tool_called, field.agent_turns, etc. are available.
--[[
Evaluation({
    runs = 3,
    parallel = true,

    dataset = {
        {
            name = "ai_research",
            inputs = {
                topic = "Artificial Intelligence"
            }
        },
        {
            name = "ml_research",
            inputs = {
                topic = "Machine Learning"
            }
        }
    },

    evaluators = {
        -- Verify search tool was called
        field.tool_called{},

        -- Verify done tool was called (by both agents)
        field.tool_called{},

        -- Verify researcher took turns
        field.agent_turns{},

        -- Verify reviewer took turns
        field.agent_turns{},

        -- Verify state was set correctly
        field.state_check{},

        -- Check output quality with LLM
        field.llm_judge{}
    }
}
)
]]--
