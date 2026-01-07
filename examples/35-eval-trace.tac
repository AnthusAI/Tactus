-- Example: Trace Inspection Evaluators
-- This demonstrates evaluators that inspect execution traces:
-- tool calls, agent turns, and state changes

Agent("researcher", {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = [[You are a research assistant.

When given a topic, search for information and then provide a summary.
1. First, call the 'search' tool with the topic
2. Then, call the 'done' tool with your findings]],
    initial_message = "Research: {topic}",
    toolsets = {"search"}
})

Agent("reviewer", {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = [[You are a quality reviewer.

Review the research and call 'done' with your assessment.]],
    initial_message = "Review this research: {research}",
})

Procedure "main" {
    input = {
        topic = field.string{required = true}
    },
    output = {
        research = field.string{required = true},
        reviewed = field.boolean{required = true}
    },
    state = {
        research_started = field.boolean{description = "Research has started", default = false}
    },
    function(input)
    -- Track state
    State.set("research_started", true)
    
    -- Researcher does the work
    Agent("researcher").turn()
    
    local research = "No research completed"
    if Tool.called("search") then
        State.set("search_completed", true)
        
        -- Get research result
        if Tool.called("done") then
            research = Tool.last_result("done") or "Task completed" or "Research done"
            State.set("research_complete", true)
        end
    end
    
    -- Reviewer checks the work
    Agent("reviewer").turn()
    
    local reviewed = Tool.called("done")
    
    return {
        research = research,
        reviewed = reviewed
    }
end
}

-- BDD Specifications
Specifications([[
Feature: Multi-Agent Research with Trace Inspection

  Scenario: Researcher searches and completes
    Given the procedure has started
    When the procedure runs
    Then the search tool should be called
    And the done tool should be called at least twice
    And the procedure should complete successfully
]])

-- Pydantic AI Evaluations with Trace Inspection
Evaluations({
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
