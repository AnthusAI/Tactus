-- Simple Agent Example
-- Demonstrates calling an LLM agent using Agent("name").turn()

-- Define completion tool using standard library
Tool "done" { use = "tactus.done" }

-- Agents (defined at top level - reusable across procedures)
Agent "greeter" {
    provider = "openai",
    system_prompt = [[You are a friendly assistant. When asked to greet someone, provide a warm, friendly greeting. When you're done, call the done tool with reason set to your greeting message.  Do not use emojis.
]],
    initial_message = "Please greet the user with a friendly message",
    toolsets = {"done"},
}

-- Procedure with outputs defined inline
Procedure "main" {
    output = {
        greeting = field.string{required = true, description = "The greeting message from the agent"},
        completed = field.boolean{required = true, description = "Whether the agent completed successfully"},
    },
    function(input)
        Log.info("Starting simple agent example")

        -- Loop until the agent calls the done tool (with max iterations for safety)
        -- This requires OPENAI_API_KEY to be set (from .tactus/config.yml or environment)
        local max_turns = 10
        local turn_count = 0

        while not Tool.called("done") and turn_count < max_turns do
            turn_count = turn_count + 1
            Log.info("Agent turn", {turn = turn_count})
            Agent("greeter").turn()
        end

        -- Check if agent called the done tool
        if Tool.called("done") then
          -- Get the last call to see what the agent passed as reason
          local call = Tool.last_call("done")
          local greeting = "Task completed"
          if call and call.args then
            -- Safely try to get reason
            local ok, reason = pcall(function() return call.args["reason"] end)
            if ok and reason then
              greeting = reason
            end
          end
          Log.info("Agent completed", {greeting = greeting, turns = turn_count})

          return {
            greeting = greeting,
            completed = true
          }
        else
          Log.warn("Agent did not call done tool after " .. turn_count .. " turns")
          return {
            greeting = "Agent did not complete properly",
            completed = false
          }
        end
    end
}

-- BDD Specifications
Specifications([[
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
