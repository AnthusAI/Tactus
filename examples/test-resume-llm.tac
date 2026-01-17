--[[
Test: LLM Checkpoint/Resume

This test verifies that LLM completions are cached and replayed deterministically
on resume. The same LLM response should be used on restart without making a new
API call.

Run with: tactus run examples/test-resume-llm.tac --storage file --storage-path /tmp/tactus-test-llm --no-sandbox
--]]

local done = require("tactus.tools.done")

haiku_agent = Agent {
    provider = "anthropic",
    model = "claude-3-5-sonnet-20241022",
    system_prompt = "You are a haiku poet. When asked, write a haiku about the given topic. Call the done tool with your haiku as the reason when finished.",
    initial_message = "Write a haiku about checkpoints in three lines.",
    tools = {done},
}

function main()
    print("Step 1: Before LLM call")

    local max_turns = 5
    local turn_count = 0

    while not done.called() and turn_count < max_turns do
        turn_count = turn_count + 1
        haiku_agent()
    end

    if done.called() then
        local call = done.last_call()
        local haiku = call.args.reason or "No haiku generated"

        print("Step 2: LLM Response received")
        print("Haiku: " .. haiku)

        return {
            haiku = haiku,
            completed = true,
            test = "llm-checkpoint-resume"
        }
    else
        print("Step 2: Agent did not complete")
        return {
            haiku = "Agent did not complete",
            completed = false,
            test = "llm-checkpoint-resume"
        }
    end
end
