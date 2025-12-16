-- DSL Toolset Integration Example
-- Demonstrates defining toolsets directly in the .tac file using the toolset() function

-- Define a custom toolset using DSL
toolset("math_tools", {
    type = "plugin",
    paths = {"./examples/tools/calculations.py"}
})

-- Agent using DSL-defined toolsets
agent("calculator", {
    provider = "openai",
    system_prompt = [[You are a helpful calculator assistant.
When asked to perform calculations, use the available tools.
When done, call the done tool with your answer.]],
    initial_message = "Calculate 15% of 200 and tell me the result",
    toolsets = {"math_tools", "done"}
})

-- Procedure demonstrating DSL toolset usage
procedure({
    outputs = {
        calculation_result = {
            type = "string",
            required = true,
            description = "The calculation result from the agent"
        },
        completed = {
            type = "boolean",
            required = true,
            description = "Whether the agent completed successfully"
        }
    }
}, function()
    Log.info("Starting DSL toolset example")

    -- Programmatic toolset access via Toolset primitive (demonstrates Toolset.get API)
    local math_toolset = Toolset.get("math_tools")
    Log.info("Retrieved math_tools toolset", {toolset = tostring(math_toolset)})
    Log.info("Note: Agent uses toolsets directly, not combined")

    -- Have the agent perform calculation with safety limit
    local max_turns = 3
    local turn_count = 0
    local result

    repeat
        result = Calculator.turn()
        turn_count = turn_count + 1
    until Tool.called("done") or turn_count >= max_turns

    -- Check if agent called done
    if Tool.called("done") then
        local answer = Tool.last_call("done").args.reason
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
end)

-- BDD Specifications
specifications([[
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
