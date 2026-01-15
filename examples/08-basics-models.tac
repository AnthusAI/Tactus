-- Multi-Model Comparison Example
-- Demonstrates using different LLM models from OpenAI, Anthropic, Meta, Amazon, and Google
-- Shows cost differences across providers and model sizes
-- Requires OpenAI API key and AWS Bedrock credentials in .tactus/config.yml (region: us-east-1)

-- Import completion tool from standard library
local done = require("tactus.tools.done")

-- Common prompt for all models
local common_prompt = "Explain quantum entanglement in exactly 2 sentences."

-- OpenAI Models
gpt4o = Agent {
    provider = "openai",
    model = "gpt-4o",
    system_prompt = "You are a physics expert. Be concise and accurate.",
    initial_message = common_prompt,
    tools = {done},
    model_settings = {
        temperature = 0.7,
        top_p = 0.9,
    }
}

gpt4o_mini = Agent {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = "You are a physics expert. Be concise and accurate.",
    initial_message = common_prompt,
    tools = {done},
    model_settings = {
        temperature = 0.7,
        top_p = 0.9,
    }
}

gpt35_turbo = Agent {
    provider = "openai",
    model = "gpt-3.5-turbo",
    system_prompt = "You are a physics expert. Be concise and accurate.",
    initial_message = common_prompt,
    tools = {done},
    model_settings = {
        temperature = 0.7,
        top_p = 0.9,
    }
}

-- Anthropic Models via Bedrock
claude_haiku = Agent {
    provider = "bedrock",
    model = "us.anthropic.claude-haiku-4-5-20251001-v1:0",
    system_prompt = "You are a physics expert. Be concise and accurate.",
    initial_message = common_prompt,
    tools = {},  -- No tools for this example
    model_settings = {
        temperature = 0.7,
    }
}

-- Meta Llama Models via Bedrock (doesn't support tool calling)
llama_8b = Agent {
    provider = "bedrock",
    model = "us.meta.llama3-1-8b-instruct-v1:0",
    system_prompt = "You are a physics expert. Be concise and accurate.",
    initial_message = common_prompt,
    tools = {},  -- Explicitly no tools
    disable_streaming = true,  -- Llama models error with tools in streaming mode
    model_settings = {
        temperature = 0.7,
    }
}

-- Models without tool support - just get direct responses
-- NOTE: Llama 3.2 3B doesn't support tool calling in AWS Bedrock's Converse API.
-- Tactus automatically detects this and configures the model profile appropriately.
llama_3b = Agent {
    provider = "bedrock",
    model = "us.meta.llama3-2-3b-instruct-v1:0",
    system_prompt = "You are a physics expert. Be concise and accurate.",
    initial_message = common_prompt,
    tools = {},  -- Explicitly no tools - this model doesn't support tool calling
    disable_streaming = true,  -- Llama models error with tools in streaming mode
    model_settings = {
        temperature = 0.7,
    }
}

nova_micro = Agent {
    provider = "bedrock",
    model = "us.amazon.nova-micro-v1:0",
    system_prompt = "You are a physics expert. Be concise and accurate.",
    initial_message = common_prompt,
    tools = {},  -- Explicitly no tools - using direct response mode
    disable_streaming = true,  -- Nova models may have issues with tools in streaming mode
    model_settings = {
        temperature = 0.7,
    }
}

nova_lite = Agent {
    provider = "bedrock",
    model = "us.amazon.nova-lite-v1:0",
    system_prompt = "You are a physics expert. Be concise and accurate.",
    initial_message = common_prompt,
    tools = {},  -- Explicitly no tools - using direct response mode
    disable_streaming = true,  -- Nova models may have issues with tools in streaming mode
    model_settings = {
        temperature = 0.7,
    }
}


-- Procedure to run all models and collect responses

Procedure {
    output = {
            result = field.string{description = "Result"}
    },
    function(input)

    Log.info("Starting multi-model comparison")

        local results = {}

        -- Helper function to run an agent with tools (uses ReAct loop)
        local function run_agent_with_tools(agent_ref, agent_name)
            Log.info("Running " .. agent_name .. "...")

            local success, result = pcall(function(input)
                -- ReAct loop for reliable tool calling
                local response_text = ""
                local max_turns = 3
                local turn_count = 0

                repeat
                    local response = agent_ref()
                    turn_count = turn_count + 1

                    if response.output and response.output ~= "" then
                        local msg = response.output
                        if type(msg) == "table" and msg.response then
                            msg = msg.response
                        end
                        if type(msg) == "string" then
                            response_text = response_text .. msg
                        end
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

            local success, result = pcall(function(input)
                local response = agent_ref()
                return {
                    response = response.output or "",
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

    -- BDD Specifications
    end
}

Specification([[
Feature: Multi-Model Comparison
  Test multiple LLM models with the same prompt

  Scenario: All models respond successfully
    Given the procedure has started
    And the agent "gpt4o" responds with "Quantum entanglement is a phenomenon where particles become correlated."
    And the agent "gpt4o" calls tool "done" with args {"reason": "Quantum entanglement explanation complete"}
    And the agent "gpt4o_mini" responds with "Entangled particles share quantum states regardless of distance."
    And the agent "gpt4o_mini" calls tool "done" with args {"reason": "Quantum physics explained"}
    And the agent "gpt35_turbo" responds with "Quantum entanglement links particles in mysterious ways."
    And the agent "gpt35_turbo" calls tool "done" with args {"reason": "Physics explanation provided"}
    And the agent "claude_haiku" responds with "Quantum entanglement connects particles across any distance instantly."
    And the agent "llama_8b" responds with "Entanglement is a key quantum mechanical phenomenon."
    And the agent "llama_3b" responds with "Particles can be entangled in their quantum states."
    And the agent "nova_micro" responds with "Quantum entanglement is fundamental to quantum computing."
    And the agent "nova_lite" responds with "Entangled particles maintain correlation regardless of separation."
    When the procedure runs
    Then the procedure should complete successfully
]])
