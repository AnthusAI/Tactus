-- AWS Bedrock Example
-- Demonstrates using Claude 4.5 Haiku via AWS Bedrock
-- Requires AWS credentials in .tactus/config.yml

-- Import completion tool from standard library
local done = require("tactus.tools.done")

-- Agent using Claude 4.5 Haiku via Bedrock (using inference profile)
haiku_assistant = Agent {
    provider = "bedrock",
    model = "us.anthropic.claude-haiku-4-5-20251001-v1:0",
    system_prompt = [[You are a helpful assistant powered by Claude 4.5 Haiku running on AWS Bedrock.

When the user asks you a question, provide a clear and concise answer.
After answering, call the done tool with a brief summary of what you explained.

IMPORTANT: Always call the done tool after providing your answer.]],
    initial_message = "What are the key benefits of using AWS Bedrock for AI applications?",
    tools = {done}
}

-- Procedure demonstrating Bedrock usage
Procedure {
    output = {
        result = field.string{description = "Result"}
    },
    function(input)
        Log.info("Testing AWS Bedrock with Claude 4.5 Haiku")

        -- ReAct loop: Keep turning until the agent calls done
        local response_text = ""
        local max_turns = 5
        local turn_count = 0

        repeat
            local response = haiku_assistant()
            turn_count = turn_count + 1

            -- Accumulate the response message from each turn
            if response.output and response.output ~= "" then
                -- Handle both string outputs and table outputs with response field
                local msg = response.output
                if type(msg) == "table" and msg.response then
                    msg = msg.response
                end
                if type(msg) == "string" then
                    response_text = response_text .. msg
                end
            end

            -- Safety check: exit if too many turns
            if turn_count >= max_turns then
                Log.warn("Max turns reached without done being called")
                break
            end
        until done.called()

        -- Extract the summary from the done tool call
        local summary = "N/A"
        if done.called() then
            summary = done.last_result() or "Task completed"
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
    end
}

-- BDD Specifications
Specification([[
Feature: AWS Bedrock Integration
  Test Claude 4.5 Haiku via AWS Bedrock

  Scenario: Bedrock agent responds successfully
    Given the procedure has started
    And the agent "haiku_assistant" responds with "AWS Bedrock provides managed access to foundation models with enterprise-grade security."
    And the agent "haiku_assistant" calls tool "done" with args {"reason": "Key benefits include scalability, security, and ease of integration"}
    When the procedure runs
    Then the done tool should be called
    And the procedure should complete successfully
]])
