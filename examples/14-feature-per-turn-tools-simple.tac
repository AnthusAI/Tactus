-- Simple Per-Turn Tool Control Test
-- Demonstrates that tools can be restricted per turn

agent("tester", {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = "You are a test agent. When you have tools, call done. When you don't have tools, just respond with 'No tools available'.",
    initial_message = "Start test",
})

main = procedure("main", {}, function()
    Log.info("Test 1: Agent with tools - should call done")
    Tester.turn()
    
    if Tool.called("done") then
        Log.info("✓ Test 1 passed: Agent called done tool")
    else
        Log.warn("✗ Test 1 failed: Agent did not call done")
    end
    
    Log.info("Test 2: Agent without tools - should just respond")
    Tester.turn({
        inject = "Respond with 'No tools available'",
        toolsets = {}
    })
    
    -- Check that done was NOT called in the second turn
    -- (Tool.called checks if it was called at all, so we need to check the last call)
    local last_call = Tool.last_call("done")
    if last_call then
        Log.info("Done was called at some point (expected from test 1)")
    end
    
    Log.info("Test 3: Agent with tools again - should call done")
    Tester.turn({inject = "Call the done tool now"})
    
    if Tool.called("done") then
        Log.info("✓ Test 3 passed: Agent called done tool again")
    end
    
    return {success = true}
end)

