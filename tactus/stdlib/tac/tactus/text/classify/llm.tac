-- LLM-Based Classification
--
-- Provides LLM-powered text classification with:
-- - Retry logic for invalid responses
-- - Multiple class support
-- - Configurable confidence modes
-- - Response parsing with fallbacks

-- Load dependencies
local base = require("tactus.text.classify.base")
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
    self.temperature = config.temperature
    self.model_id = config.model or "openai/gpt-4o-mini"
    self.confidence_mode = config.confidence_mode or "heuristic"

    -- Build Model primitive instance.
    -- Note: in mocked mode, Mocks { <model_name> = ... } can override this call
    -- deterministically without spinning up any real provider interactions.
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
    -- Validate the predicted value against the explicit class set. If invalid,
    -- retry by calling the model again. This makes retry_count meaningful and
    -- keeps the contract stable across mocked and real runs.
    local valid_lower = {}
    for _, v in ipairs(self.classes) do
        valid_lower[v:lower()] = v
    end

    local function safe_get(obj, key)
        if obj == nil then
            return nil
        end
        if type(obj) == "table" then
            return obj[key]
        end
        local ok, value = pcall(function()
            return obj[key]
        end)
        if ok then
            return value
        end
        return nil
    end

    local last_output = nil
    for attempt = 1, self.max_retries + 1 do
        local result = self.model({text = input_text})
        -- Unwrap Model primitive PredictionResult safely (works for both Lua tables
        -- and Python-backed objects bridged into Lua).
        local output = result
        local ok, maybe_output = pcall(function()
            return result["output"]
        end)
        if ok and maybe_output ~= nil then
            output = maybe_output
        elseif type(result) == "table" and result.output ~= nil then
            output = result.output
        end
        last_output = output

        local value = safe_get(output, "value") or safe_get(output, "sentiment")
        if value == nil and type(output) == "string" then
            value = self:parse_response(output)
        end

        local canonical = nil
        if value ~= nil then
            canonical = valid_lower[tostring(value):lower()]
        end

        if canonical ~= nil then
            local response = {
                value = canonical,
                retry_count = attempt - 1,
                raw_response = output,
            }
            local conf = safe_get(output, "confidence")
            if conf ~= nil then
                response.confidence = conf
            elseif self.confidence_mode == "heuristic" then
                response.confidence = 0.8
            end
            local expl = safe_get(output, "explanation")
            if expl ~= nil then
                response.explanation = expl
            end
            return response
        end
    end

    return {
        value = "ERROR",
        retry_count = self.max_retries,
        raw_response = last_output,
        error = "Invalid classification after retries",
    }
end

-- Export LLMClassifier
return {
    LLMClassifier = LLMClassifier,
}
