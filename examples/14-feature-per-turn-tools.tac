-- Per-Turn Tool Control Example
-- Demonstrates dynamic tool availability for specific turns

agent("researcher", {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = "You are a research assistant. Use tools to gather information.",
    initial_message = "Start researching the topic",
})

procedure({
    input = {
        topic = {
            type = "string",
            required = false,
            default = "artificial intelligence",
            description = "Topic to research"
        }
    },
    output = {
        summary = {
            type = "string",
            required = true
        }
    },
    state = {}
}, function()
    Log.info("Starting research", {topic = input.topic})
    
    repeat
        -- Main turn: agent has all tools (done in this simple example)
        Researcher.turn()
        
        -- After the agent calls done, ask for a summary with NO tools
        -- This demonstrates the key pattern: restricting tools for specific turns
        if Tool.called("done") then
            Log.info("Agent called done, requesting summary without tools")
            Researcher.turn({
                inject = "Provide a brief summary of what you just did in 1-2 sentences",
                toolsets = {}  -- No tools for summarization turn
            })
        end
        
    until Tool.called("done") or Iterations.exceeded(20)
    
    -- Final creative summary with temperature override
    Log.info("Requesting final creative summary")
    Researcher.turn({
        inject = "Provide a final creative summary of all findings",
        toolsets = {},
        temperature = 0.9
    })
    
    return {
        summary = "Research completed on: " .. input.topic
    }
end)

specifications([[
Feature: Per-Turn Tool Control
  Demonstrate dynamic tool availability

  Scenario: Agent uses tools then summarizes without tools
    Given the procedure has started
    When the procedure runs
    Then the done tool should be called
    And the total iterations should be greater than 1
    And the procedure should complete successfully
]])

