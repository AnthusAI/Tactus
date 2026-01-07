-- Example: Optional State Declaration
-- Demonstrates that state = {} is no longer required in procedures

-- Standard library done tool
Tool "done" { use = "tactus.done" }

-- Agent for demonstration
Agent "assistant" {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = "You are a helpful assistant. When asked to demonstrate something, explain it briefly and call done.",
    toolsets = {"done"}
}

-- Procedure WITHOUT state declaration (new optional syntax)
Procedure "simple_demo" {
    input = {
        message = field.string{default = "Hello World"}
    },
    output = {
        result = field.string{required = true}
    },
    -- Notice: No state = {} declaration needed!
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
Procedure "main" {
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

        Agent("assistant").turn({initial_message = agent_message})

        -- Wait for done
        local max_turns = 3
        local turn_count = 1
        while not Tool.called("done") and turn_count < max_turns do
            Agent("assistant").turn()
            turn_count = turn_count + 1
        end

        return {
            result = result,
            message = message
        }
    end
}

-- BDD Specifications
Specifications([[
Feature: Optional State Declaration
  Procedures no longer require empty state = {} declarations

  Scenario: Simple procedure without state works
    Given the procedure has started
    When the procedure runs with demo_type "simple"
    Then the procedure should complete successfully
    And the output message should be "No state declaration was needed!"

  Scenario: Stateful procedure with state works
    Given the procedure has started
    When the procedure runs with demo_type "stateful"
    Then the procedure should complete successfully
    And the output result should contain "Stateful demo count"
]])