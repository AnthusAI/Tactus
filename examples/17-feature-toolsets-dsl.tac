-- DSL Toolset Integration Example
-- Demonstrates defining toolsets directly in the .tac file using the toolset() function

-- Define completion tool
Tool "done" { use = "tactus.done" }

-- Define math tools
Tool "multiply" {
    description = "Multiply two numbers",
    input = {
        a = field.number{required = true},
        b = field.number{required = true}
    },
    function(args)
        return args.a * args.b
    end
}

Tool "percentage" {
    description = "Calculate percentage of a number",
    input = {
        value = field.number{required = true, description = "The value"},
        percent = field.number{required = true, description = "The percentage"}
    },
    function(args)
        return args.value * (args.percent / 100)
    end
}

-- Define a custom toolset using DSL
Toolset "math_tools" {
    tools = {"multiply", "percentage"}
}

-- Agent using DSL-defined toolsets
Agent "calculator" {
    provider = "openai",
    system_prompt = [[You are a helpful calculator assistant.
When asked to perform calculations, use the available tools.

IMPORTANT: To calculate 15% of 200, use the percentage tool with these exact parameters:
- value: 200 (the number to calculate percentage of)
- percent: 15 (the percentage amount)

When done, call the done tool with your answer.]],
    initial_message = "Calculate 15% of 200 and tell me the result",
    toolsets = {"multiply", "percentage", "done"}
}

-- Procedure demonstrating DSL toolset usage

output {
        calculation_result = field.string{required = true, description = "The calculation result from the agent"},
        completed = field.boolean{required = true, description = "Whether the agent completed successfully"}
    }

Log.info("Starting DSL toolset example")

    -- Note: Toolset.get() API is not yet implemented
    -- The agent can use toolsets directly via the toolsets parameter
    Log.info("Note: Agent uses toolsets directly via toolsets parameter")

    -- Have the agent perform calculation with safety limit
    local max_turns = 3
    local turn_count = 0
    local result

    repeat
        result = Agent("calculator").turn()
        turn_count = turn_count + 1
    until Tool.called("done") or turn_count >= max_turns

    -- Check if agent called done
    if Tool.called("done") then
        local call = Tool.last_call("done")
        local answer = "Task completed"
        if call and call.args then
            -- Safely try to get reason
            local ok, reason = pcall(function() return call.args["reason"] end)
            if ok and reason then
                answer = reason
            end
        end
        Log.info("Agent completed calculation", {result = answer})

        return {
            calculation_result = answer,
            completed = true
        }
    else
        Log.warn("Agent did not call done within max turns")
        return {
            calculation_result = result.text or "Agent did not complete",
            completed = false
        }
    end

-- BDD Specifications
Specifications([[
Feature: DSL Toolset Integration
  Demonstrate defining and using toolsets via the DSL

  Scenario: Agent uses DSL-defined toolsets
    Given the procedure has started
    When the procedure runs
    Then the done tool should be called
    And the procedure should complete successfully
    And the output completed should be True
    And the output calculation_result should exist
]])
