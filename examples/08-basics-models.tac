-- Multi-Model Comparison Example
-- Demonstrates using different LLM models from OpenAI, Anthropic, Meta, Amazon, and Google
-- Shows cost differences across providers and model sizes
-- Requires OpenAI API key and AWS Bedrock credentials in .tactus/config.yml (region: us-east-1)

-- Common prompt for all models
local common_prompt = "Explain quantum entanglement in exactly 2 sentences."

-- OpenAI Models
agent("gpt4o", {
    provider = "openai",
    model = "gpt-4o",
    system_prompt = "You are a physics expert. Be concise and accurate.",
    initial_message = common_prompt,
    tools = {"done"},
    model_settings = {
        temperature = 0.7,
        top_p = 0.9,
    }
})

agent("gpt4o_mini", {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = "You are a physics expert. Be concise and accurate.",
    initial_message = common_prompt,
    tools = {"done"},
    model_settings = {
        temperature = 0.7,
        top_p = 0.9,
    }
})

agent("gpt35_turbo", {
    provider = "openai",
    model = "gpt-3.5-turbo",
    system_prompt = "You are a physics expert. Be concise and accurate.",
    initial_message = common_prompt,
    tools = {"done"},
    model_settings = {
        temperature = 0.7,
        top_p = 0.9,
    }
})

-- Anthropic Models via Bedrock
agent("claude_haiku", {
    provider = "bedrock",
    model = "us.anthropic.claude-haiku-4-5-20251001-v1:0",
    system_prompt = "You are a physics expert. Be concise and accurate.",
    initial_message = common_prompt,
    toolsets = {},  -- No tools for this example
    model_settings = {
        temperature = 0.7,
    }
})

-- Meta Llama Models via Bedrock (doesn't support tool calling)
agent("llama_8b", {
    provider = "bedrock",
    model = "us.meta.llama3-1-8b-instruct-v1:0",
    system_prompt = "You are a physics expert. Be concise and accurate.",
    initial_message = common_prompt,
    toolsets = {},  -- Explicitly no tools
    disable_streaming = true,  -- Llama models error with tools in streaming mode
    model_settings = {
        temperature = 0.7,
    }
})

-- Models without tool support - just get direct responses
-- NOTE: Llama 3.2 3B doesn't support tool calling in AWS Bedrock's Converse API.
-- Tactus automatically detects this and configures the model profile appropriately.
agent("llama_3b", {
    provider = "bedrock",
    model = "us.meta.llama3-2-3b-instruct-v1:0",
    system_prompt = "You are a physics expert. Be concise and accurate.",
    initial_message = common_prompt,
    toolsets = {},  -- Explicitly no tools - this model doesn't support tool calling
    disable_streaming = true,  -- Llama models error with tools in streaming mode
    model_settings = {
        temperature = 0.7,
    }
})

agent("nova_micro", {
    provider = "bedrock",
    model = "us.amazon.nova-micro-v1:0",
    system_prompt = "You are a physics expert. Be concise and accurate.",
    initial_message = common_prompt,
    toolsets = {},  -- Explicitly no tools - using direct response mode
    disable_streaming = true,  -- Nova models may have issues with tools in streaming mode
    model_settings = {
        temperature = 0.7,
    }
})

agent("nova_lite", {
    provider = "bedrock",
    model = "us.amazon.nova-lite-v1:0",
    system_prompt = "You are a physics expert. Be concise and accurate.",
    initial_message = common_prompt,
    toolsets = {},  -- Explicitly no tools - using direct response mode
    disable_streaming = true,  -- Nova models may have issues with tools in streaming mode
    model_settings = {
        temperature = 0.7,
    }
})


-- Procedure to run all models and collect responses
main = procedure("main", function()
    Log.info("Starting multi-model comparison")
    
    local results = {}
    
    -- Helper function to run an agent with tools (uses ReAct loop)
    local function run_agent_with_tools(agent_ref, agent_name)
        Log.info("Running " .. agent_name .. "...")

        local success, result = pcall(function()
            -- ReAct loop for reliable tool calling
            local response_text = ""
            local max_turns = 3
            local turn_count = 0

            repeat
                local response = agent_ref.turn()
                turn_count = turn_count + 1

                if response.text and response.text ~= "" then
                    response_text = response_text .. response.text
                end

                if turn_count >= max_turns then
                    Log.warn(agent_name .. ": Max turns reached")
                    break
                end
            until Tool.called("done")

            return {
                response = response_text,
                turns = turn_count,
                success = Tool.called("done"),
                error = nil
            }
        end)

        if not success then
            Log.warn(agent_name .. " failed: " .. tostring(result))
            return {
                response = "",
                turns = 0,
                success = false,
                error = tostring(result)
            }
        end

        return result
    end
    
    -- Helper function to run an agent without tools (single turn)
    local function run_agent_no_tools(agent_ref, agent_name)
        Log.info("Running " .. agent_name .. "...")

        local success, result = pcall(function()
            local response = agent_ref.turn()
            return {
                response = response.text or "",
                turns = 1,
                success = true,
                error = nil
            }
        end)

        if not success then
            Log.warn(agent_name .. " failed: " .. tostring(result))
            return {
                response = "",
                turns = 0,
                success = false,
                error = tostring(result)
            }
        end

        return result
    end
    
    -- Run models with tool support (OpenAI only)
    results.gpt4o = run_agent_with_tools(Gpt4o, "GPT-4o")
    results.gpt4o_mini = run_agent_with_tools(Gpt4o_mini, "GPT-4o-mini")
    results.gpt35_turbo = run_agent_with_tools(Gpt35_turbo, "GPT-3.5-turbo")

    -- Run models without tool support (Bedrock, Llama, Nova)
    results.claude_haiku = run_agent_no_tools(Claude_haiku, "Claude 4.5 Haiku")
    results.llama_8b = run_agent_no_tools(Llama_8b, "Llama 3.1 8B")
    results.llama_3b = run_agent_no_tools(Llama_3b, "Llama 3.2 3B")
    results.nova_micro = run_agent_no_tools(Nova_micro, "Nova Micro")
    results.nova_lite = run_agent_no_tools(Nova_lite, "Nova Lite")
    
    Log.info("All models completed!")
    
    return {
        prompt = common_prompt,
        models = {
            "gpt-4o",
            "gpt-4o-mini", 
            "gpt-3.5-turbo",
            "claude-haiku-4-5",
            "llama-3-1-8b",
            "llama-3-2-3b",
            "nova-micro",
            "nova-lite"
        },
        results = results,
        total_models = 12
    }
end)

-- BDD Specifications
specifications([[
Feature: Multi-Model Comparison
  Test multiple LLM models with the same prompt

  Scenario: All models respond successfully
    Given the procedure has started
    When the procedure runs
    Then the done tool should be called at least 5 times
    And the procedure should complete successfully
    And the result should include responses from 8 models
]])

