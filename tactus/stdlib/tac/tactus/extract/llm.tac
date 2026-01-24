-- LLM-Based Extraction
--
-- Provides LLM-powered structured data extraction with:
-- - Retry logic for invalid responses
-- - JSON parsing and validation
-- - Field type validation
-- - Conversational feedback for self-correction

-- Load dependencies
local base = require("tactus.extract.base")
local BaseExtractor = base.BaseExtractor
local class = base.class
local json = require("tactus.io.json")

-- ============================================================================
-- LLMExtractor
-- ============================================================================

local LLMExtractor = class(BaseExtractor)

function LLMExtractor:init(config)
    BaseExtractor.init(self, config)

    -- Validate required fields
    assert(config.fields, "LLMExtractor requires 'fields' field")
    assert(config.prompt, "LLMExtractor requires 'prompt' field")

    self.fields = config.fields
    self.prompt = config.prompt
    self.max_retries = config.max_retries or 3
    self.temperature = config.temperature or 0.3
    self.model = config.model
    self.strict = config.strict ~= false  -- Default to strict mode

    -- Build extraction system prompt
    self.system_prompt = self:build_system_prompt()

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

function LLMExtractor:build_system_prompt()
    -- Build fields description
    local fields_lines = {}
    for name, type_ in pairs(self.fields) do
        table.insert(fields_lines, string.format("  - %s: %s", name, type_))
    end
    local fields_description = table.concat(fields_lines, "\n")

    return string.format([[You are an information extraction assistant. Your task is to extract structured data according to the following instruction:

%s

FIELDS TO EXTRACT:
%s

IMPORTANT RULES:
1. You MUST respond with a valid JSON object containing the extracted fields.
2. Include ONLY the specified fields in your response.
3. Use null for fields that cannot be extracted from the input.
4. For "number" fields, return numeric values (not strings).
5. For "list" fields, return JSON arrays.
6. For "boolean" fields, return true or false.
7. Do NOT include any explanation or text outside the JSON.

RESPONSE FORMAT:
{
  "field1": "extracted value",
  "field2": 123,
  ...
}]], self.prompt, fields_description)
end

function LLMExtractor:parse_json(response)
    if not response or response == "" then
        return nil, {"Empty response"}
    end

    -- Try to find JSON object in response
    local json_start = response:find("{")
    local json_end = response:reverse():find("}")

    if not json_start or not json_end then
        return nil, {"No JSON object found in response"}
    end

    json_end = #response - json_end + 1
    local json_str = response:sub(json_start, json_end)

    -- Parse JSON using the json global
    local success, parsed = pcall(function()
        return json.decode(json_str)
    end)

    if not success then
        return nil, {"Invalid JSON: " .. tostring(parsed)}
    end

    return parsed, {}
end

function LLMExtractor:extract(input_text)
    local retry_count = 0
    local last_response = nil
    local validation_errors = {}

    for attempt = 1, self.max_retries + 1 do
        -- Build message for this attempt
        local message
        if attempt == 1 then
            message = "Please extract the following information:\n\n" .. input_text
        else
            -- Retry with feedback
            retry_count = retry_count + 1
            message = self:build_retry_feedback(last_response, validation_errors)
        end

        -- Call agent
        local agent_result = self.agent({message = message})
        last_response = agent_result.output or ""

        -- Parse and validate response
        local parsed, parse_errors = self:parse_json(last_response)

        if #parse_errors > 0 then
            validation_errors = parse_errors
        else
            -- Validate extracted fields against schema
            local result, val_errors = self:validate_fields(parsed, self.fields)
            validation_errors = val_errors

            if #validation_errors == 0 then
                return {
                    fields = result,
                    retry_count = retry_count,
                    raw_response = last_response
                }
            end
        end
    end

    -- All retries exhausted
    return {
        fields = {},
        error = string.format("Max retries (%d) exceeded. Validation errors: %s",
            self.max_retries, table.concat(validation_errors, ", ")),
        retry_count = retry_count,
        validation_errors = validation_errors,
        raw_response = last_response
    }
end

function LLMExtractor:build_retry_feedback(last_response, errors)
    local errors_str = table.concat(errors, "\n  - ")
    local fields_list = {}
    for name, _ in pairs(self.fields) do
        table.insert(fields_list, '"' .. name .. '"')
    end
    local fields_str = table.concat(fields_list, ", ")

    -- Truncate long responses
    local response_preview = last_response
    if #response_preview > 500 then
        response_preview = response_preview:sub(1, 500) .. "..."
    end

    return string.format([[Your previous response was not valid JSON or had validation errors.

Previous response:
%s

Errors:
  - %s

Please respond with ONLY a valid JSON object containing these fields: %s

Do NOT include any explanation or text outside the JSON object.]],
        response_preview, errors_str, fields_str)
end

function LLMExtractor:__call(text)
    return self:extract(text)
end

-- Export LLMExtractor
return {
    LLMExtractor = LLMExtractor,
}
