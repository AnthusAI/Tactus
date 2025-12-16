-- Google Gemini Example
-- Demonstrates using Gemini 3 Pro and Gemini 2.0 Flash
-- Note: Gemini 3 Flash doesn't appear to be available yet via API
-- Requires GOOGLE_API_KEY in .tactus/config.yml

-- Agent using Gemini 3 Pro (most capable model)
agent("gemini_pro", {
    provider = "google-gla",
    model = "gemini-3-pro-preview",
    system_prompt = [[You are a helpful assistant powered by Google Gemini 3 Pro.

When the user asks you a question, provide a clear and comprehensive answer.
After answering, call the done tool with a brief summary of what you explained.

IMPORTANT: Always call the done tool after providing your answer.]],
    initial_message = "What are the key benefits of using Google Gemini for AI applications?",
    toolsets = {"done"}
})

-- Agent using Gemini 2.0 Flash (fast, efficient model)
agent("gemini_flash", {
    provider = "google-gla",
    model = "gemini-2.0-flash-exp",
    system_prompt = [[You are a helpful assistant powered by Google Gemini 2.0 Flash.

When the user asks you a question, provide a detailed and comprehensive answer.
After answering, call the done tool with a brief summary of what you explained.

IMPORTANT: Always call the done tool after providing your answer.]],
    initial_message = "Explain the key advantages of using Gemini Flash for fast AI responses.",
    toolsets = {"done"}
})

-- Procedure demonstrating multiple Gemini models
procedure(function()
    Log.info("Testing Google Gemini with multiple models")

    local max_turns = 3

    -- Test Gemini 3 Pro
    Log.info("=== Testing Gemini 3 Pro ===")
    local pro_response = ""
    local pro_turns = 0

    repeat
        local response = Gemini_pro.turn()
        pro_turns = pro_turns + 1

        -- Accumulate the response text
        if response.text and response.text ~= "" then
            pro_response = pro_response .. response.text
        end

        -- Safety check
        if pro_turns >= max_turns then
            Log.warn("Max turns reached for Gemini 3 Pro")
            break
        end
    until Tool.called("done")

    local pro_summary = "N/A"
    if Tool.called("done") then
        pro_summary = Tool.last_call("done").args.reason
        Log.info("Gemini 3 Pro test complete!", {summary = pro_summary})
    end

    -- Reset tool state before next agent
    Tool.reset()

    -- Test Gemini 2.0 Flash
    Log.info("=== Testing Gemini 2.0 Flash ===")
    local flash_response = ""
    local flash_turns = 0

    repeat
        local response = Gemini_flash.turn()
        flash_turns = flash_turns + 1

        -- Accumulate the response text
        if response.text and response.text ~= "" then
            flash_response = flash_response .. response.text
        end

        -- Safety check
        if flash_turns >= max_turns then
            Log.warn("Max turns reached for Gemini 2.0 Flash")
            break
        end
    until Tool.called("done")

    local flash_summary = "N/A"
    if Tool.called("done") then
        flash_summary = Tool.last_call("done").args.reason
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
end)

-- BDD Specifications
specifications([[
Feature: Google Gemini Integration
  Test multiple Gemini models

  Scenario: Flash model responds successfully
    Given the procedure has started
    When the procedure runs
    Then the done tool should be called at least once
    And the procedure should complete successfully

  Scenario: Both models complete
    Given the procedure has started
    When the procedure runs
    Then the done tool should be called at least 2 times
    And the procedure should complete successfully
]])
