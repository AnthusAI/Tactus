-- Example: Optional State Declaration
-- Demonstrates that state = {} is no longer required in procedures

-- Import completion tool from standard library
local done = require("tactus.tools.done")

-- Agent for demonstration
assistant = Agent {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = "You are a helpful assistant. When asked to demonstrate something, explain it briefly and call done.",
    tools = {done}
}

-- Procedure WITHOUT state declaration (new optional syntax)
Procedure "simple_demo" {
    input = {
        message = field.string{default = "Hello World"}
    },
    output = {
        result = field.string{required = true}
    },
    function(input)
        Log.info("Processing message", {message = input.message})
        return {
            result = "Processed: " .. input.message
        }
    end
}

-- Another procedure that actually uses state (must declare it)
Procedure "stateful_demo" {
    state = {
        counter = field.integer{default = 0}
    },
    output = {
        count = field.integer{required = true}
    },
    function(input)
        State.counter = State.counter + 1
        return {
            count = State.counter
        }
    end
}

-- Main procedure (also without state)
Procedure {
    input = {
        demo_type = field.string{
            default = "simple",
            description = "Type of demo: simple or stateful"
        }
    },
    output = {
        result = field.string{required = true},
        message = field.string{required = true}
    },
    function(input)
        local result
        local message

        if input.demo_type == "stateful" then
            local res = Procedure("stateful_demo")({})
            result = "Stateful demo count: " .. tostring(res.count)
            message = "State was used and incremented"
        else
            local res = Procedure("simple_demo")({message = "Testing optional state"})
            result = res.result
            message = "No state declaration was needed!"
        end

        -- Call agent for explanation
        local agent_message = string.format(
            "Demonstrate that procedures in Tactus no longer require empty state = {} declarations. " ..
            "We just ran a %s demo. The result was: %s",
            input.demo_type, result
        )

        assistant({message = agent_message})

        -- Wait for done
        local max_turns = 3
        local turn_count = 1
        while not done.called() and turn_count < max_turns do
            assistant()
            turn_count = turn_count + 1
        end

        return {
            result = result,
            message = message
        }
    end
}

Specification([[
Feature: Optional State Declaration
  Procedures no longer require empty state = {} declarations

  Scenario: Simple procedure without state works
    Given the procedure has started
    And the agent "assistant" responds with "State declarations are optional - you only need to declare state if you actually use it."
    And the agent "assistant" calls tool "done" with args {"reason": "Demonstrated that state declarations are now optional in Tactus procedures."}
    When the procedure runs
    Then the done tool should be called
    And the output result should exist
    And the output message should exist
    And the procedure should complete successfully
]])
