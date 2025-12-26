-- Simple Agent Example
-- Demonstrates calling an LLM agent using Worker.turn()

-- Agents (defined at top level - reusable across procedures)
agent("greeter", {
    provider = "openai",
    system_prompt = [[You are a friendly assistant. When asked to greet someone, 
provide a warm, friendly greeting. When you're done, call 
the done tool with the greeting message.
]],
    initial_message = "Please greet the user with a friendly message",
})

-- Procedure with outputs defined inline
main = procedure("main", {
    outputs = {
        greeting = {
            type = "string",
            required = true,
            description = "The greeting message from the agent",
        },
        completed = {
            type = "boolean",
            required = true,
            description = "Whether the agent completed successfully",
        },
    }
}, function()
    Log.info("Starting simple agent example")

    -- Have the agent turn once (calls LLM)
    -- This requires OPENAI_API_KEY to be set (from .tactus/config.yml or environment)
    Greeter.turn()

    -- Check if agent called the done tool
    if Tool.called("done") then
      local greeting = Tool.last_call("done").args.reason
      Log.info("Agent completed", {greeting = greeting})
  
      return {
        greeting = greeting,
        completed = true
      }
    else
      Log.warn("Agent did not call done tool")
      return {
        greeting = "Agent did not complete properly",
        completed = false
      }
    end
end)

-- BDD Specifications
specifications([[
Feature: Simple Agent Interaction
  Demonstrate basic LLM agent interaction with done tool

  Scenario: Agent generates greeting using real LLM
    Given the procedure has started
    When the procedure runs
    Then the done tool should be called
    And the procedure should complete successfully
    And the output completed should be True
    And the output greeting should exist
    And the output greeting should not be "Agent did not complete properly"
    And the output greeting should match pattern "(Hello|Hi|Greetings|Welcome|hello|hi|greetings|welcome)"
]])
