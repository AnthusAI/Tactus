-- LLM-Based Classification
--
-- Provides LLM-powered text classification with:
-- - Retry logic for invalid responses
-- - Multiple class support
-- - Configurable confidence modes
-- - Response parsing with fallbacks

-- Load dependencies
local base = require("tactus.classify.base")
local BaseClassifier = base.BaseClassifier
local class = base.class
local models = require("tactus.models.llm")

-- ============================================================================
-- LLMClassifier
-- ============================================================================

local LLMClassifier = class(BaseClassifier)

function LLMClassifier:init(config)
    BaseClassifier.init(self, config)

    -- Validate required fields
    assert(config.classes, "LLMClassifier requires 'classes' field")
    assert(config.prompt, "LLMClassifier requires 'prompt' field")

    self.name = config.name
    self.classes = config.classes
    self.prompt = config.prompt
    self.max_retries = config.max_retries or 3
    self.temperature = config.temperature or 0.3
    self.model_id = config.model
    self.confidence_mode = config.confidence_mode or "heuristic"

    -- Build Model primitive instance
    self.model = models.LLMModel {
        name = self.name or "llm_classifier",
        classes = self.classes,
        prompt = self.prompt,
        model = self.model_id,
        temperature = self.temperature,
        retries = self.max_retries,
        parse_direction = "end",
    }
end

function LLMClassifier:parse_response(response)
    if not response or response == "" then
        return nil
    end

    -- Get first line
    local first_line = response:match("^([^\n]+)")
    if not first_line then
        first_line = response
    end

    -- Clean up formatting
    first_line = first_line:gsub("[%*\"'`:%.]", ""):gsub("^%s+", ""):gsub("%s+$", "")
    local first_line_lower = first_line:lower()

    -- Create case-insensitive lookup
    local value_map = {}
    for _, v in ipairs(self.classes) do
        value_map[v:lower()] = v
    end

    -- Exact match (case-insensitive)
    if value_map[first_line_lower] then
        return value_map[first_line_lower]
    end

    -- Prefix match
    for v_lower, v_original in pairs(value_map) do
        if first_line_lower:find("^" .. v_lower) then
            return v_original
        end
    end

    return nil
end

function LLMClassifier:classify(input_text)
    local result = self.model({text = input_text})
    local output = result.output or result
    local value = output.value or output.sentiment or self:parse_response(output)

    local response = {
        value = value,
        retry_count = result.retry_count or 0,
        raw_response = output,
    }

    if output.confidence then
        response.confidence = output.confidence
    elseif self.confidence_mode == "heuristic" then
        response.confidence = 0.8
    end

    return response
end

-- Export LLMClassifier
return {
    LLMClassifier = LLMClassifier,
}
