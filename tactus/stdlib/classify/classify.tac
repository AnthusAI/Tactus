-- Classification Classes with Proper Inheritance
--
-- This implements a proper Lua class hierarchy for classifiers:
-- - BaseClassifier (abstract base)
-- - LLMClassifier (LLM-based classification)
-- - FuzzyMatchClassifier (string similarity)

-- Simple class system for Lua
local function class(base)
    local c = {}
    if base then
        for k, v in pairs(base) do
            c[k] = v
        end
        c._base = base
    end
    c.__index = c

    function c:new(config)
        local instance = setmetatable({}, self)
        if instance.init then
            instance:init(config)
        end
        return instance
    end

    return c
end

-- ============================================================================
-- BaseClassifier (Abstract Base Class)
-- ============================================================================

BaseClassifier = class()

function BaseClassifier:init(config)
    self.config = config or {}
end

function BaseClassifier:classify(text)
    error("BaseClassifier.classify() must be implemented by subclass")
end

function BaseClassifier:__call(text)
    return self:classify(text)
end

-- ============================================================================
-- LLMClassifier
-- ============================================================================

LLMClassifier = class(BaseClassifier)

function LLMClassifier:init(config)
    BaseClassifier.init(self, config)

    -- Validate required fields
    assert(config.classes, "LLMClassifier requires 'classes' field")
    assert(config.prompt, "LLMClassifier requires 'prompt' field")

    self.classes = config.classes
    self.prompt = config.prompt
    self.max_retries = config.max_retries or 3
    self.temperature = config.temperature or 0.3
    self.model = config.model
    self.confidence_mode = config.confidence_mode or "heuristic"

    -- Build classification prompt
    local classes_str = table.concat(self.classes, ", ")
    self.system_prompt = string.format([[%s

You MUST respond with ONLY one of these values: %s

Response format:
- Start your response with the classification value on its own line
- You may optionally explain your reasoning afterward

Valid values: %s]], self.prompt, classes_str, classes_str)

    -- Create agent
    local agent_config = {
        system_prompt = self.system_prompt,
        temperature = self.temperature,
    }

    if self.model then
        local provider, model_id = self.model:match("([^/]+)/(.+)")
        if provider and model_id then
            agent_config.provider = provider
            agent_config.model = model_id
        end
    end

    self.agent = Agent(agent_config)
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
    local retry_count = 0
    local last_response = nil

    for attempt = 1, self.max_retries + 1 do
        -- Call agent
        local agent_result = self.agent:turn({input = input_text})
        last_response = agent_result.message or agent_result.content or ""

        -- Parse classification
        local value = self:parse_response(last_response)

        if value then
            local result = {
                value = value,
                retry_count = retry_count,
                raw_response = last_response
            }

            if self.confidence_mode == "heuristic" then
                result.confidence = 0.8
            end

            return result
        end

        -- Retry
        retry_count = retry_count + 1

        if attempt <= self.max_retries then
            local feedback = string.format(
                "Your response '%s' is not valid. Please respond with ONLY one of: %s",
                last_response,
                table.concat(self.classes, ", ")
            )
            self.agent:turn({input = feedback})
        end
    end

    -- All retries exhausted
    return {
        value = "ERROR",
        error = "Failed to get valid classification after " .. self.max_retries .. " retries",
        retry_count = retry_count,
        raw_response = last_response
    }
end

-- ============================================================================
-- FuzzyMatchClassifier
-- ============================================================================

FuzzyMatchClassifier = class(BaseClassifier)

function FuzzyMatchClassifier:init(config)
    BaseClassifier.init(self, config)

    assert(config.expected, "FuzzyMatchClassifier requires 'expected' field")

    self.expected = config.expected
    self.threshold = config.threshold or 0.8
    self.classes = config.classes or {"Yes", "No"}
end

function FuzzyMatchClassifier:calculate_similarity(s1, s2)
    s1 = s1:lower()
    s2 = s2:lower()

    if s1 == s2 then
        return 1.0
    end

    if s1:find(s2, 1, true) or s2:find(s1, 1, true) then
        return 0.85
    end

    -- Character overlap similarity
    local set1 = {}
    for i = 1, #s1 do
        set1[s1:sub(i,i)] = true
    end

    local intersection = 0
    local set2 = {}
    for i = 1, #s2 do
        local char = s2:sub(i,i)
        set2[char] = true
        if set1[char] then
            intersection = intersection + 1
        end
    end

    local union = 0
    for _ in pairs(set1) do union = union + 1 end
    for char in pairs(set2) do
        if not set1[char] then
            union = union + 1
        end
    end

    if union == 0 then
        return 0.0
    end

    return intersection / union
end

function FuzzyMatchClassifier:classify(input_text)
    local similarity = self:calculate_similarity(input_text, self.expected)
    local value = similarity >= self.threshold and self.classes[1] or self.classes[2]

    return {
        value = value,
        confidence = similarity,
        matched_text = self.expected,  -- What it matched against
        retry_count = 0
    }
end

-- Export classes
return {
    BaseClassifier = BaseClassifier,
    LLMClassifier = LLMClassifier,
    FuzzyMatchClassifier = FuzzyMatchClassifier,
}
