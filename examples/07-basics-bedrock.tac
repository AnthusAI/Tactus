-- AWS Bedrock Example
-- Demonstrates using Claude 4.5 Haiku via AWS Bedrock
-- Requires AWS credentials in .tactus/config.yml

-- Agent using Claude 4.5 Haiku via Bedrock (using inference profile)
agent("haiku_assistant", {
    provider = "bedrock",
    model = "us.anthropic.claude-haiku-4-5-20251001-v1:0",
    system_prompt = [[You are a helpful assistant powered by Claude 4.5 Haiku running on AWS Bedrock.

When the user asks you a question, provide a clear and concise answer.
After answering, call the done tool with a brief summary of what you explained.

IMPORTANT: Always call the done tool after providing your answer.]],
    initial_message = "What are the key benefits of using AWS Bedrock for AI applications?",
    toolsets = {"done"}
})

-- Procedure demonstrating Bedrock usage
procedure(function()
    Log.info("Testing AWS Bedrock with Claude 4.5 Haiku")

    -- ReAct loop: Keep turning until the agent calls done
    local response_text = ""
    local max_turns = 5
    local turn_count = 0

    repeat
        local response = Haiku_assistant.turn()
        turn_count = turn_count + 1

        -- Accumulate the response text from each turn using .text property
        if response.text and response.text ~= "" then
            response_text = response_text .. response.text
        end

        -- Safety check: exit if too many turns
        if turn_count >= max_turns then
            Log.warn("Max turns reached without done being called")
            break
        end
    until Tool.called("done")

    -- Extract the summary from the done tool call
    local summary = "N/A"
    if Tool.called("done") then
        summary = Tool.last_call("done").args.reason
        Log.info("Bedrock test complete!", {summary = summary})
    else
        Log.warn("Test incomplete - done tool not called")
    end

    return {
        provider = "bedrock",
        model = "us.anthropic.claude-haiku-4-5-20251001-v1:0",
        response = response_text,
        summary = summary,
        turns = turn_count,
        success = Tool.called("done")
    }
end)

-- BDD Specifications
specifications([[
Feature: AWS Bedrock Integration
  Test Claude 4.5 Haiku via AWS Bedrock

  Scenario: Bedrock agent responds successfully
    Given the procedure has started
    When the procedure runs
    Then the done tool should be called
    And the procedure should complete successfully
]])

