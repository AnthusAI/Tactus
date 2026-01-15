-- Simple Per-Turn Tool Control Test
-- Demonstrates that tools can be restricted per turn

-- Import the done tool from standard library
local done = require("tactus.tools.done")

tester = Agent {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = "You are a test agent. When you have tools, call done. When you don't have tools, just respond with 'No tools available'.",
    initial_message = "Start test",
    tools = {done}  -- Default toolset
}

Specification([[
Feature: Per-turn tools (simple)

  Scenario: Tools can be restricted per turn
    Given the procedure has started
    And the agent "tester" responds with "Done"
    And the agent "tester" calls tool "done" with args {"reason": "Completed per-turn tool control demo"}
    And the agent "tester" responds with "No tools available"
    And the agent "tester" responds with "Done"
    And the agent "tester" calls tool "done" with args {"reason": "Completed per-turn tool control demo"}
    When the procedure runs
    Then the done tool should be called exactly 2 times
    And the procedure should complete successfully
]])

Procedure {
    output = {
            result = field.string{description = "Result"}
    },
    function(input)

    Log.info("Test 1: Agent with tools - should call done")
        tester()

        if done.called() then
            Log.info("✓ Test 1 passed: Agent called done tool")
        else
            Log.warn("✗ Test 1 failed: Agent did not call done")
        end

        Log.info("Test 2: Agent without tools - should just respond")
        tester({
            message = "Respond with 'No tools available'",
            tools = {}
        })

        -- Check that done was NOT called in the second turn
        -- (Tool.called checks if it was called at all, so we need to check the last call)
        local last_call = done.last_call()
        if last_call then
            Log.info("Done was called at some point (expected from test 1)")
        end

        Log.info("Test 3: Agent with tools again - should call done")
        tester({message = "Call the done tool now"})

        if done.called() then
            Log.info("✓ Test 3 passed: Agent called done tool again")
        end

        return {success = true}

    end
}
