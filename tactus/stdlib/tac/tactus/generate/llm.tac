-- LLM-Based Text Generation
--
-- Provides flexible text generation with DSPy-inspired features:
-- - Configurable prompts and system instructions
-- - Optional chain-of-thought reasoning
-- - Output format control (text, JSON, markdown)
-- - Retry logic for invalid responses
-- - Few-shot examples support (future optimization)

-- Load dependencies
local base = require("tactus.generate.base")
local BaseGenerator = base.BaseGenerator
local class = base.class

-- ============================================================================
-- LLMGenerator
-- ============================================================================

local LLMGenerator = class(BaseGenerator)

function LLMGenerator:init(config)
    BaseGenerator.init(self, config)

    -- Build system prompt (without reasoning - ChainOfThought handles that)
    local full_system_prompt = self:build_system_prompt()

    -- Create agent configuration
    -- Default: "Raw" module (no prompt modifications)
    -- With reasoning: "ChainOfThought" module (DSPy's reasoning)
    local agent_config = {
        system_prompt = full_system_prompt,
        temperature = self.temperature,
    }

    -- Use ChainOfThought module when reasoning is enabled
    -- Otherwise, Agent defaults to "Raw" (no prompt modifications)
    if self.reasoning then
        agent_config.module = "ChainOfThought"
    end

    -- Parse model string (e.g., "openai/gpt-4o-mini")
    if self.model then
        local provider, model_id = self.model:match("([^/]+)/(.+)")
        if provider and model_id then
            agent_config.provider = provider
            agent_config.model = model_id
        end
    end

    -- Add max_tokens if specified
    if self.max_tokens then
        agent_config.max_tokens = self.max_tokens
    end

    if self.name then
        self.agent = Agent(self.name)(agent_config)
    else
        self.agent = Agent(agent_config)
    end
end

function LLMGenerator:generate(prompt)
    local retry_count = 0
    local last_response = nil
    local last_error = nil

    for attempt = 1, self.max_retries + 1 do
        -- Call agent
        local ok, agent_result = pcall(function()
            return self.agent({message = prompt})
        end)

        if not ok then
            last_error = agent_result
            retry_count = retry_count + 1
        else
            local output = agent_result.output
            local response_text = nil
            local reasoning_text = nil

            -- Handle different output formats from DSPy modules
            if type(output) == "table" then
                -- ChainOfThought returns {reasoning: ..., response: ...}
                response_text = tostring(output.response or "")
                reasoning_text = output.reasoning and tostring(output.reasoning) or nil
                last_response = response_text
            else
                -- Raw module returns plain text
                response_text = tostring(output or "")
                last_response = response_text

                -- For raw mode with reasoning enabled, try to parse structured output
                -- (This handles edge cases where manual reasoning format was used)
                if self.reasoning and type(response_text) == "string" then
                    local parsed = self:parse_reasoning_response(response_text)
                    response_text = parsed.response
                    reasoning_text = parsed.reasoning
                end
            end

            -- Validate response based on format
            local valid = self:validate_response(response_text)

            if valid then
                return {
                    output = response_text,
                    reasoning = reasoning_text,
                    format = self.output_format,
                    retry_count = retry_count,
                    raw_response = last_response
                }
            end

            retry_count = retry_count + 1
        end
    end

    -- All retries exhausted
    return {
        output = last_response or "",
        reasoning = nil,
        format = self.output_format,
        retry_count = retry_count,
        error = last_error or "Failed to generate valid response after " .. self.max_retries .. " retries",
        raw_response = last_response
    }
end

function LLMGenerator:validate_response(response)
    -- Ensure response is a string
    if response == nil then
        return false
    end

    -- Convert to string if needed (handles Python objects)
    local response_str = tostring(response)

    -- Basic validation - ensure we got something
    if #response_str == 0 then
        return false
    end

    -- JSON format validation
    if self.output_format == "json" then
        -- Try to detect valid JSON (basic check)
        local trimmed = response_str:gsub("^%s+", ""):gsub("%s+$", "")

        -- Should start with { or [
        if not (trimmed:match("^%{") or trimmed:match("^%[")) then
            return false
        end

        -- Should end with } or ]
        if not (trimmed:match("%}$") or trimmed:match("%]$")) then
            return false
        end
    end

    return true
end

function LLMGenerator:__call(prompt)
    return self:generate(prompt)
end

-- Export LLMGenerator
return {
    LLMGenerator = LLMGenerator,
}
