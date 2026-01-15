-- Simple Agent Example

local done = require("tactus.tools.done")

greeter = Agent {
    provider = "openai",
    model = "gpt-5-mini",
    model_type = "responses",  -- Required for reasoning models (o3, gpt-5 series)
    temperature = 1.0,         -- Reasoning models require temperature=1.0
    max_tokens = 16000,        -- Reasoning models require max_tokens >= 16000
    system_prompt = "You are a friendly assistant. When asked to greet someone, provide a warm, friendly greeting. When you're done, call the done tool with reason set to your greeting message. Do not use emojis.",
    initial_message = "Please greet the user with a friendly message",
    tools = {done},
}

Procedure {
    output = {
            greeting = field.string{required = true},
            completed = field.boolean{required = true},
    },
    function(input)

    local max_turns = 10
            local turn_count = 0

            while not done.called() and turn_count < max_turns do
                turn_count = turn_count + 1
                greeter()
            end

            if done.called() then
                local call = done.last_call()
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

    -- BDD Specifications
    end
}

Specification([[
Feature: Simple Agent Interaction
  Demonstrate basic LLM agent interaction with done tool

  Scenario: Agent generates greeting using real LLM
    Given the procedure has started
    And the agent "greeter" responds with "Hello! Welcome! I hope you have a wonderful day."
    And the agent "greeter" calls tool "done" with args {"reason": "Hello! Welcome! I hope you have a wonderful day."}
    When the procedure runs
    Then the done tool should be called
    And the procedure should complete successfully
    And the output completed should be True
    And the output greeting should exist
    And the output greeting should not be "Agent did not complete properly"
    And the output greeting should match pattern "(Hello|Hi|Greetings|Welcome|hello|hi|greetings|welcome)"
]])
