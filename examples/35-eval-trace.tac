-- Example: Trace Inspection Evaluators
-- This demonstrates evaluators that inspect execution traces:
-- tool calls, agent turns, and state changes

agent("researcher", {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = [[You are a research assistant.

When given a topic, search for information and then provide a summary.
1. First, call the 'search' tool with the topic
2. Then, call the 'done' tool with your findings]],
    initial_message = "Research: {topic}",
    toolsets = {"search"}
})

agent("reviewer", {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = [[You are a quality reviewer.

Review the research and call 'done' with your assessment.]],
    initial_message = "Review this research: {research}",
})

procedure({
    input = {
        topic = {
            type = "string",
            required = true
        }
    },
    output = {
        research = {
            type = "string",
            required = true
        },
        reviewed = {
            type = "boolean",
            required = true
        }
    },
    state = {
        research_started = {
            type = "boolean",
            default = false,
            description = "Research has started"
        }
    }
}, function()
    -- Track state
    State.set("research_started", true)
    
    -- Researcher does the work
    Researcher.turn()
    
    local research = "No research completed"
    if Tool.called("search") then
        State.set("search_completed", true)
        
        -- Get research result
        if Tool.called("done") then
            research = Tool.last_call("done").args.reason or "Research done"
            State.set("research_complete", true)
        end
    end
    
    -- Reviewer checks the work
    Reviewer.turn()
    
    local reviewed = Tool.called("done")
    
    return {
        research = research,
        reviewed = reviewed
    }
end)

-- BDD Specifications
specifications([[
Feature: Multi-Agent Research with Trace Inspection

  Scenario: Researcher searches and completes
    Given the procedure has started
    When the procedure runs
    Then the search tool should be called
    And the done tool should be called at least twice
    And the procedure should complete successfully
]])

-- Pydantic AI Evaluations with Trace Inspection
evaluations({
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
        {
            type = "tool_called",
            value = "search",
            min_value = 1,
            max_value = 2
        },
        
        -- Verify done tool was called (by both agents)
        {
            type = "tool_called",
            value = "done",
            min_value = 2,
            max_value = 2
        },
        
        -- Verify researcher took turns
        {
            type = "agent_turns",
            field = "researcher",
            min_value = 1,
            max_value = 3
        },
        
        -- Verify reviewer took turns
        {
            type = "agent_turns",
            field = "reviewer",
            min_value = 1,
            max_value = 2
        },
        
        -- Verify state was set correctly
        {
            type = "state_check",
            field = "research_complete",
            value = true
        },
        
        -- Check output quality with LLM
        {
            type = "llm_judge",
            rubric = [[
Score 1.0 if:
- Research was conducted
- Output is coherent and relevant
- Both agents participated

Score 0.0 otherwise.
            ]],
            model = "openai:gpt-4o-mini"
        }
    }
})
