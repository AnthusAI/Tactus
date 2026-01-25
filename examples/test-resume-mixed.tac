--[[
Test: Mixed Operations (LLM + HITL) with Checkpoint/Resume

This test verifies that checkpoint/resume works correctly when mixing
LLM calls (agent) and HITL calls (Human.*) in the same procedure.

Pattern tested: LLM → HITL → LLM → HITL

Run with: tactus run examples/test-resume-mixed.tac --storage file --storage-path /tmp/tactus-test-mixed --no-sandbox
--]]

local done = require("tactus.tools.done")

-- Agent for generating content
content_agent = Agent {
    provider = "anthropic",
    model = "claude-3-5-sonnet-20241022",
    system_prompt = "You are a helpful assistant. Generate short, concise responses. Call the done tool with your response as the reason when finished.",
    tools = {done},
}

function main()
    print("=== Mixed Operations Test ===")
    print("")

    -- Step 1: LLM generates a product name
    print("Step 1: LLM generates product name")
    content_agent.initial_message = "Generate a creative name for a todo app in 2-3 words."

    local max_turns = 3
    local turn_count = 0

    while not done.called() and turn_count < max_turns do
        turn_count = turn_count + 1
        content_agent()
    end

    local product_name = "Unknown Product"
    if done.called() then
        local call = done.last_call()
        product_name = call.args.reason or "Unknown Product"
        print("  Generated: " .. product_name)
    else
        print("  Agent did not complete")
    end

    done.reset()

    -- Step 2: Human approves the name
    print("")
    print("Step 2: Human reviews product name")
    local approved_name = Human.approve({
        message = "Approve product name: '" .. product_name .. "'?",
        default = true
    })
    print("  Approved: " .. tostring(approved_name))

    if not approved_name then
        print("  User rejected name. Stopping.")
        return {
            product_name = product_name,
            approved_name = false,
            tagline = nil,
            approved_tagline = false,
            test = "mixed-operations-rejected"
        }
    end

    -- Step 3: LLM generates a tagline
    print("")
    print("Step 3: LLM generates tagline")
    content_agent.initial_message = "Write a catchy one-sentence tagline for a product called '" .. product_name .. "'."

    turn_count = 0
    while not done.called() and turn_count < max_turns do
        turn_count = turn_count + 1
        content_agent()
    end

    local tagline = "No tagline generated"
    if done.called() then
        local call = done.last_call()
        tagline = call.args.reason or "No tagline generated"
        print("  Generated: " .. tagline)
    else
        print("  Agent did not complete")
    end

    done.reset()

    -- Step 4: Human approves the tagline
    print("")
    print("Step 4: Human reviews tagline")
    local approved_tagline = Human.approve({
        message = "Approve tagline: '" .. tagline .. "'?",
        default = true
    })
    print("  Approved: " .. tostring(approved_tagline))

    print("")
    print("=== Test Complete ===")

    return {
        product_name = product_name,
        approved_name = approved_name,
        tagline = tagline,
        approved_tagline = approved_tagline,
        test = "mixed-operations-complete"
    }
end
