-- Google Gemini Example
-- Demonstrates using Gemini 3 Pro and Gemini 2.0 Flash
-- Note: Gemini 3 Flash doesn't appear to be available yet via API
-- Requires GOOGLE_API_KEY in .tactus/config.yml

-- Import completion tool from standard library
local done = require("tactus.tools.done")

-- Agent using Gemini 3 Pro (most capable model)
gemini_pro = Agent {
    provider = "google-gla",
    model = "gemini-3-pro-preview",
    system_prompt = [[You are a helpful assistant powered by Google Gemini 3 Pro.

When the user asks you a question, provide a clear and comprehensive answer.
After answering, call the done tool with a brief summary of what you explained.

IMPORTANT: Always call the done tool after providing your answer.]],
    initial_message = "What are the key benefits of using Google Gemini for AI applications?",
    tools = {done}
}

-- Agent using Gemini 2.0 Flash (fast, efficient model)
gemini_flash = Agent {
    provider = "google-gla",
    model = "gemini-2.0-flash-exp",
    system_prompt = [[You are a helpful assistant powered by Google Gemini 2.0 Flash.

When the user asks you a question, provide a detailed and comprehensive answer.
After answering, call the done tool with a brief summary of what you explained.

IMPORTANT: Always call the done tool after providing your answer.]],
    initial_message = "Explain the key advantages of using Gemini Flash for fast AI responses.",
    tools = {done}
}

-- Procedure demonstrating multiple Gemini models

Procedure {
    output = {
            result = field.string{description = "Result"}
    },
    function(input)

    Log.info("Testing Google Gemini with multiple models")

        local max_turns = 3

        -- Test Gemini 3 Pro
        Log.info("=== Testing Gemini 3 Pro ===")
        local pro_response = ""
        local pro_turns = 0

        repeat
            local response = gemini_pro()
            pro_turns = pro_turns + 1

            -- Accumulate the response text
            if response.output and response.output ~= "" then
                local msg = response.output
                if type(msg) == "table" and msg.response then
                    msg = msg.response
                end
                if type(msg) == "string" then
                    pro_response = pro_response .. msg
                end
            end

            -- Safety check
            if pro_turns >= max_turns then
                Log.warn("Max turns reached for Gemini 3 Pro")
                break
            end
        until done.called()

        local pro_summary = "N/A"
        if done.called() then
            pro_summary = done.last_result() or "Task completed"
            Log.info("Gemini 3 Pro test complete!", {summary = pro_summary})
        end

        -- Reset tool state before next agent
        Tool.reset()

        -- Test Gemini 2.0 Flash
        Log.info("=== Testing Gemini 2.0 Flash ===")
        local flash_response = ""
        local flash_turns = 0

        repeat
            local response = gemini_flash()
            flash_turns = flash_turns + 1

            -- Accumulate the response text
            if response.output and response.output ~= "" then
                local msg = response.output
                if type(msg) == "table" and msg.response then
                    msg = msg.response
                end
                if type(msg) == "string" then
                    flash_response = flash_response .. msg
                end
            end

            -- Safety check
            if flash_turns >= max_turns then
                Log.warn("Max turns reached for Gemini 2.0 Flash")
                break
            end
        until done.called()

        local flash_summary = "N/A"
        if done.called() then
            flash_summary = done.last_result() or "Task completed"
            Log.info("Gemini 2.0 Flash test complete!", {summary = flash_summary})
        end

        return {
            provider = "google-gla",
            models_tested = {
                gemini_3_pro = {
                    model = "gemini-3-pro-preview",
                    response = pro_response,
                    summary = pro_summary,
                    turns = pro_turns
                },
                gemini_2_flash = {
                    model = "gemini-2.0-flash-exp",
                    response = flash_response,
                    summary = flash_summary,
                    turns = flash_turns
                }
            },
            success = true
        }

    -- BDD Specifications
    end
}

Specification([[
Feature: Google Gemini Integration
  Test multiple Gemini models

  Scenario: Gemini models respond successfully
    Given the procedure has started
    And the agent "gemini_pro" responds with "Google Gemini provides powerful AI capabilities for various applications."
    And the agent "gemini_pro" calls tool "done" with args {"reason": "Gemini Pro offers advanced reasoning and multimodal capabilities"}
    And the agent "gemini_flash" responds with "Gemini Flash is optimized for speed and efficiency."
    And the agent "gemini_flash" calls tool "done" with args {"reason": "Flash offers fast responses with lower latency"}
    When the procedure runs
    Then the done tool should be called at least 1 time
    And the procedure should complete successfully
]])
