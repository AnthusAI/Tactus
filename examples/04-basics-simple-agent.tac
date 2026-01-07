-- Simple Agent Example

Tool "done" { use = "tactus.done" }

Agent "greeter" {
    provider = "openai",
    model = "gpt-5-mini",
    system_prompt = "You are a friendly assistant. When asked to greet someone, provide a warm, friendly greeting. When you're done, call the done tool with reason set to your greeting message. Do not use emojis.",
    initial_message = "Please greet the user with a friendly message",
    toolsets = {"done"},
}

Procedure "main" {
    output = {
        greeting = field.string{required = true},
        completed = field.boolean{required = true},
    },
    function(input)
        local max_turns = 10
        local turn_count = 0

        while not Tool.called("done") and turn_count < max_turns do
            turn_count = turn_count + 1
            Agent("greeter").turn()
        end

        if Tool.called("done") then
            local call = Tool.last_call("done")
            return {
                greeting = call.args.reason or "Hello!",
                completed = true
            }
        else
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
