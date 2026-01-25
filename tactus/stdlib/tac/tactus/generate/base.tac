-- Base Generator Module
--
-- Provides the BaseGenerator abstract class and class helper for
-- building custom generator implementations.
--
-- Inspired by DSPy's modular generation approach:
-- - Configurable generation parameters
-- - Optional chain-of-thought reasoning
-- - Output format control
-- - Retry logic for robustness

-- ============================================================================
-- Class Helper (same pattern as classify/extract modules)
-- ============================================================================

local function class(base)
    local cls = {}
    cls.__index = cls

    if base then
        setmetatable(cls, {__index = base})
    end

    function cls:new(config)
        local instance = setmetatable({}, cls)
        if instance.init then
            instance:init(config or {})
        end
        return instance
    end

    return cls
end

-- ============================================================================
-- BaseGenerator
-- ============================================================================

local BaseGenerator = class()

function BaseGenerator:init(config)
    -- Core configuration
    self.name = config.name
    self.model = config.model
    self.temperature = config.temperature or 0.7
    self.max_tokens = config.max_tokens
    self.max_retries = config.max_retries or 2

    -- Generation options (DSPy-inspired)
    self.reasoning = config.reasoning or false  -- Chain-of-thought mode
    self.output_format = config.output_format or "text"  -- "text", "json", "markdown"
    self.constraints = config.constraints  -- Output constraints (optional)

    -- System prompt and instructions
    self.system_prompt = config.system_prompt
    self.instructions = config.instructions
end

function BaseGenerator:generate(prompt)
    error("BaseGenerator:generate() must be implemented by subclass")
end

function BaseGenerator:__call(prompt)
    return self:generate(prompt)
end

-- ============================================================================
-- Helper functions for subclasses
-- ============================================================================

-- Build system prompt
-- Note: Reasoning is handled by DSPy's ChainOfThought module, not manual prompts
function BaseGenerator:build_system_prompt()
    local parts = {}

    -- Base system prompt
    if self.system_prompt then
        table.insert(parts, self.system_prompt)
    else
        table.insert(parts, "You are a helpful assistant.")
    end

    -- Note: reasoning is NOT added to system prompt here
    -- When reasoning=true, we use DSPy's ChainOfThought module which handles
    -- reasoning automatically without modifying the prompt

    -- Add output format instructions
    if self.output_format == "json" then
        table.insert(parts, "Respond with valid JSON only. No markdown formatting or code blocks.")
    elseif self.output_format == "markdown" then
        table.insert(parts, "Format your response using Markdown.")
    end

    -- Add custom instructions
    if self.instructions then
        table.insert(parts, self.instructions)
    end

    -- Add constraints
    if self.constraints then
        if type(self.constraints) == "table" then
            table.insert(parts, "Constraints: " .. table.concat(self.constraints, ", "))
        else
            table.insert(parts, "Constraints: " .. self.constraints)
        end
    end

    return table.concat(parts, "\n\n")
end

-- Parse response to extract reasoning and final response
function BaseGenerator:parse_reasoning_response(response)
    if not self.reasoning then
        return {
            response = response,
            reasoning = nil
        }
    end

    -- Try to extract REASONING and RESPONSE sections
    local reasoning = response:match("REASONING:%s*(.-)%s*RESPONSE:")
    local final_response = response:match("RESPONSE:%s*(.*)$")

    if reasoning and final_response then
        return {
            response = final_response:gsub("^%s+", ""):gsub("%s+$", ""),
            reasoning = reasoning:gsub("^%s+", ""):gsub("%s+$", "")
        }
    end

    -- If pattern doesn't match, return whole response
    return {
        response = response,
        reasoning = nil
    }
end

-- Export BaseGenerator and class helper
return {
    BaseGenerator = BaseGenerator,
    class = class,
}
