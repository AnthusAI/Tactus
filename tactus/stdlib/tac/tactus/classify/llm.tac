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

-- ============================================================================
-- LLMClassifier
-- ============================================================================

local LLMClassifier = class(BaseClassifier)

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
        local agent_result = self.agent({message = input_text})
        last_response = agent_result.output or ""

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
            self.agent({message = feedback})
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

-- Export LLMClassifier
return {
    LLMClassifier = LLMClassifier,
}
